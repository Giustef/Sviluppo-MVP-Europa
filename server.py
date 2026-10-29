"""Demo locale autenticata: account di prova, nessun invio esterno. Python >=3.11."""
import json, os, secrets, sqlite3, time, uuid, sys, io, hashlib, hmac, threading, argparse, getpass
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'vendor'))
DB=os.environ.get('EUROPA_DB',str(ROOT/'demo.sqlite3'))
SESSIONS={}
AUTH_LOCK=threading.Lock()
LOGIN_ATTEMPTS={}
SESSION_TTL=3600
MAX_SESSIONS=1000
ROLES={'participant','staff','organizer','restaurant','admin'}
class Problem(Exception):
 def __init__(self,status,message): self.status,self.message=status,message

def connect():
 c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init():
 with connect() as c:
  tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if tables and ('metadata' not in tables or [r[0] for r in c.execute('SELECT version FROM metadata')]!=[2]):
   raise RuntimeError('Database demo v0.1 incompatibile: conservarne un backup e usare un nuovo EUROPA_DB. Nessuna migrazione automatica di identità simulate.')
  c.executescript((ROOT/'schema.sql').read_text())
 os.chmod(DB,0o600)

def password_hash(password, salt=None):
 salt=salt or secrets.token_hex(16)
 digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=131072,r=8,p=1,maxmem=256*1024*1024).hex()
 return salt+':'+digest

DUMMY_HASH=password_hash('unavailable-account-dummy')

def create_user(username,password,role,tenant):
 if not isinstance(username,str) or not 3<=len(username)<=80 or not username.isascii() or not all(x.isalnum() or x in '._-' for x in username):
  raise ValueError('Username: 3–80 caratteri ASCII, lettere, numeri, punto, trattino o underscore')
 if not isinstance(password,str) or not 12<=len(password)<=256 or role not in ROLES or tenant not in {'club-demo','club-other'}:
  raise ValueError('Password di 12–256 caratteri, ruolo e organizzazione validi richiesti')
 with connect() as c:
  c.execute('INSERT INTO users(id,username,password_hash,role,tenant) VALUES(?,?,?,?,?)',(uuid.uuid4().hex,username,password_hash(password),role,tenant))

def authenticate(username,password,address):
 now=time.time()
 with AUTH_LOCK:
  for k in list(LOGIN_ATTEMPTS):
   if LOGIN_ATTEMPTS[k][0]<now-300: del LOGIN_ATTEMPTS[k]
  if address not in LOGIN_ATTEMPTS and len(LOGIN_ATTEMPTS)>=10000: raise Problem(429,'Riprova più tardi')
  started,count=LOGIN_ATTEMPTS.get(address,(now,0))
  if count>=10: raise Problem(429,'Troppi tentativi: riprova tra cinque minuti')
  LOGIN_ATTEMPTS[address]=(started,count+1)
 if not isinstance(username,str) or not isinstance(password,str) or len(username)>80 or len(password)>256:
  raise Problem(401,'Credenziali non valide')
 with connect() as c: row=c.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
 stored=row['password_hash'] if row else DUMMY_HASH
 valid=hmac.compare_digest(password_hash(password,stored.split(':')[0]),stored)
 if not row or not valid: raise Problem(401,'Credenziali non valide')
 return {'user':row['id'],'role':row['role'],'tenant':row['tenant']}

def check_runtime(mode,host):
 if mode!='demo': raise RuntimeError('Produzione bloccata: questo pacchetto include pagamenti e assistenza simulati')
 if host not in {'127.0.0.1','localhost'}: raise RuntimeError('Demo consentita soltanto su loopback; nessuna esposizione LAN o Internet')

def audit(c,s,action,entity): c.execute('INSERT INTO audit(actor,action,entity,created) VALUES(?,?,?,?)',(s['user'],action,entity,time.time()))

def require(s,roles):
 if s['role'] not in roles: raise Problem(403,'Ruolo non autorizzato')

def event(c,s,eid):
 r=c.execute('SELECT * FROM events WHERE id=? AND tenant=?',(eid,s['tenant'])).fetchone()
 if not r: raise Problem(404,'Evento non disponibile')
 return dict(r)

def operate(s,action,b):
 if action=='me': return s
 eid=b.get('event_id','other' if s['tenant']=='club-other' else 'salento')
 if not isinstance(eid,str) or not 1<=len(eid)<=100: raise Problem(400,'Evento non valido')
 if action in {'approve','reject','pay','ack','close'} and (not isinstance(b.get('id'),str) or not 1<=len(b['id'])<=100): raise Problem(400,'Identificativo non valido')
 if action=='scan' and (not isinstance(b.get('token'),str) or len(b['token'])>200): raise Problem(400,'Codice non valido')
 if action=='close' and not isinstance(b.get('reason'),str): raise Problem(400,'Motivazione non valida')
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  e=event(c,s,eid)
  c.execute("UPDATE registrations SET state='expired' WHERE event_id=? AND state='held' AND expires<?",(eid,time.time()))
  if action=='state':
   regs=[dict(x) for x in c.execute('SELECT * FROM registrations WHERE event_id=?',(eid,))]
   own=[r for r in regs if r['owner']==s['user']]
   if s['role']=='participant': regs=own
   if s['role'] in {'restaurant','staff'}: regs=[]
   incidents=[]
   if s['role'] in {'staff','organizer','admin'}: incidents=[dict(x) for x in c.execute('SELECT * FROM incidents WHERE event_id=? ORDER BY created DESC',(eid,))]
   elif s['role']=='participant': incidents=[dict(x) for x in c.execute('SELECT * FROM incidents WHERE event_id=? AND actor=?',(eid,s['user']))]
   paid=c.execute("SELECT COUNT(*) n,COALESCE(SUM(amount),0) amount,COALESCE(SUM(meal),0) meals FROM registrations WHERE event_id=? AND state='paid'",(eid,)).fetchone()
   meals=c.execute("SELECT COUNT(*) FROM scans s JOIN registrations r ON r.id=s.registration_id WHERE r.event_id=? AND service='meal'",(eid,)).fetchone()[0]
   return {'event':e,'registrations':regs,'incidents':incidents,'totals':{'paid':paid['n'],'amount':paid['amount'] if s['role'] in {'organizer','admin'} else None,'booked_meals':paid['meals'],'consumed':meals},'demo':True}
  if action=='register':
   require(s,{'participant','organizer','admin'})
   if not isinstance(b.get('name'),str) or not isinstance(b.get('key'),str): raise Problem(400,'Nome e chiave devono essere stringhe')
   name=b['name'].strip(); key=b['key']
   if not 2<=len(name)<=100 or not 8<=len(key)<=100 or type(b.get('meal')) is not bool: raise Problem(400,'Nome, opzione pasto o chiave non validi')
   idem=key
   old=c.execute('SELECT * FROM registrations WHERE event_id=? AND owner=? AND idem=?',(eid,s['user'],idem)).fetchone()
   if old: return dict(old)
   rid=uuid.uuid4().hex
   c.execute('INSERT INTO registrations VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,eid,s['user'],name,int(b['meal']),'requested',0,e['price'] if b['meal'] else 1500,secrets.token_urlsafe(32),idem))
   audit(c,s,'registration.requested',rid)
   return dict(c.execute('SELECT * FROM registrations WHERE id=?',(rid,)).fetchone())
  if action in {'approve','reject'}:
   require(s,{'organizer','admin'})
   r=c.execute('SELECT * FROM registrations WHERE id=? AND event_id=?',(b.get('id'),eid)).fetchone()
   if not r or r['state']!='requested': raise Problem(409,'Richiesta non disponibile')
   if action=='approve':
    used=c.execute("SELECT COUNT(*),COALESCE(SUM(meal),0) FROM registrations WHERE event_id=? AND state IN ('held','paid')",(eid,)).fetchone()
    if used[0]>=e['capacity'] or r['meal'] and used[1]>=e['meal_capacity']: raise Problem(409,'Capienza esaurita')
   state='held' if action=='approve' else 'rejected'
   c.execute('UPDATE registrations SET state=?,expires=? WHERE id=?',(state,time.time()+600 if state=='held' else 0,r['id']))
   audit(c,s,'registration.'+action,r['id'])
   return dict(c.execute('SELECT * FROM registrations WHERE id=?',(r['id'],)).fetchone())
  if action=='pay':
   require(s,{'participant','organizer','admin'})
   if type(b.get('success')) is not bool: raise Problem(400,'Esito simulato booleano richiesto')
   r=c.execute('SELECT * FROM registrations WHERE id=? AND event_id=?',(b.get('id'),eid)).fetchone()
   if not r or s['role']=='participant' and r['owner']!=s['user']: raise Problem(404,'Iscrizione non disponibile')
   if r['state']=='paid': return {'state':'paid','simulated':True}
   if r['state']!='held': raise Problem(409,'Prenotazione non pagabile')
   state='paid' if b.get('success') is True else 'failed'
   c.execute('UPDATE registrations SET state=? WHERE id=?',(state,r['id']))
   c.execute('INSERT INTO payments VALUES(?,?,?,?)',(uuid.uuid4().hex,r['id'],state,r['amount']))
   audit(c,s,'payment.simulated.'+state,r['id']); return {'state':state,'simulated':True}
  if action=='scan':
   require(s,{'staff','restaurant','organizer','admin'})
   service=b.get('service','meal')
   if service not in {'meal','event'} or s['role']=='restaurant' and service!='meal': raise Problem(403,'Servizio non autorizzato')
   r=c.execute('SELECT * FROM registrations WHERE token=? AND event_id=?',(b.get('token'),eid)).fetchone()
   if not r or r['state']!='paid' or service=='meal' and not r['meal']: raise Problem(400,'Pass non valido per questo servizio')
   try: c.execute('INSERT INTO scans VALUES(?,?,?,?,?)',(uuid.uuid4().hex,r['id'],service,s['user'],time.time()))
   except sqlite3.IntegrityError: raise Problem(409,'Pass già utilizzato: nessun coperto aggiunto')
   audit(c,s,'checkin.'+service,r['id']); return {'accepted':True}
  if action=='sos':
   require(s,{'participant','staff','organizer','admin'})
   key=b.get('key','')
   if not isinstance(key,str) or not 8<=len(key)<=100: raise Problem(400,'Chiave richiesta')
   lat,lon,acc=b.get('lat'),b.get('lon'),b.get('accuracy')
   if (lat is None)!=(lon is None): raise Problem(400,'Coordinate incomplete')
   if lat is not None and (type(lat) not in (float,int) or type(lon) not in (float,int) or not -90<=lat<=90 or not -180<=lon<=180): raise Problem(400,'Coordinate non valide')
   if acc is not None and (type(acc) not in (float,int) or not 0<=acc<=100000): raise Problem(400,'Accuratezza non valida')
   idem=key
   old=c.execute('SELECT * FROM incidents WHERE event_id=? AND actor=? AND idem=?',(eid,s['user'],idem)).fetchone()
   if old: return dict(old)
   iid=uuid.uuid4().hex
   c.execute('INSERT INTO incidents(id,event_id,actor,message,lat,lon,accuracy,state,assignee,created,idem) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(iid,eid,s['user'],str(b.get('message','Richiesta assistenza demo'))[:500],lat,lon,acc,'received',None,time.time(),idem))
   c.execute('INSERT INTO notifications(id,incident_id) VALUES(?,?)',(uuid.uuid4().hex,iid));audit(c,s,'sos.received',iid)
   return {'id':iid,'state':'received','notification':'available_in_staff_demo_inbox','public_emergency_services_contacted':False}
  if action in {'ack','close'}:
   require(s,{'staff','organizer','admin'})
   r=c.execute('SELECT * FROM incidents WHERE id=? AND event_id=?',(b.get('id'),eid)).fetchone()
   if not r: raise Problem(404,'SOS non disponibile')
   if action=='close' and (r['state']!='acknowledged' or len(str(b.get('reason','')).strip())<5): raise Problem(409,'Prima prendere in carico e indicare una motivazione')
   if action=='ack' and r['state']!='received': raise Problem(409,'SOS già assegnato o chiuso')
   state='acknowledged' if action=='ack' else 'closed'
   if action=='ack': c.execute('UPDATE incidents SET state=?,assignee=? WHERE id=?',(state,s['user'],r['id']))
   else:
    if r['assignee']!=s['user'] and s['role'] not in {'organizer','admin'}: raise Problem(403,'Chiusura consentita al responsabile o amministratore/organizzatore')
    reason=str(b.get('reason','')).strip()
    if len(reason)>500: raise Problem(400,'Motivazione troppo lunga')
    c.execute('UPDATE incidents SET state=?,closed_by=?,closed_at=?,close_reason=? WHERE id=?',(state,s['user'],time.time(),reason,r['id']))
   audit(c,s,'sos.'+state,r['id']);return {'state':state}
  raise Problem(404,'Operazione sconosciuta')

class Handler(BaseHTTPRequestHandler):
 def setup(self):
  super().setup();self.connection.settimeout(10)
 def send(self,status,data,kind='application/json',cookie=None):
  raw=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
  if cookie: self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(raw)
 def session(self):
  cookie=SimpleCookie(self.headers.get('Cookie',''));sid=cookie.get('europa_session')
  with AUTH_LOCK:
   s=SESSIONS.get(sid.value if sid else '')
   if not s or s['expires']<=time.time():
    if sid: SESSIONS.pop(sid.value,None)
    raise Problem(401,'Accedi con il tuo account')
  with connect() as c: active=c.execute('SELECT 1 FROM users WHERE id=? AND role=? AND tenant=? AND active=1',(s['user'],s['role'],s['tenant'])).fetchone()
  if not active: raise Problem(401,'Account non disponibile')
  return s
 def check_host(self):
  if self.headers.get('Host') not in self.server.allowed_hosts: raise Problem(403,'Host non consentito')
 def check_origin(self):
  origin=self.headers.get('Origin')
  if origin and origin!='http://'+self.headers.get('Host',''): raise Problem(403,'Origine non consentita')
 def do_GET(self):
  try: self.check_host()
  except Problem as e: self.send(e.status,{'error':e.message});return
  path=self.path.split('?')[0]
  if path.startswith('/api/qr/'):
   try:
    import qrcode, qrcode.image.svg
    s=self.session();rid=path.rsplit('/',1)[-1]
    with connect() as c:
     r=c.execute("SELECT r.* FROM registrations r JOIN events e ON e.id=r.event_id WHERE r.id=? AND e.tenant=? AND r.state='paid'",(rid,s['tenant'])).fetchone()
     if not r or s['role'] not in {'participant','organizer','admin'} or s['role']=='participant' and r['owner']!=s['user']: raise Problem(404,'Pass non disponibile')
     out=io.BytesIO();qrcode.make(r['token'],image_factory=qrcode.image.svg.SvgPathImage).save(out)
     self.send(200,out.getvalue(),'image/svg+xml')
   except Problem as e: self.send(e.status,{'error':e.message})
   return
  if path=='/api/state':
   try: self.send(200,operate(self.session(),'state',{}))
   except Problem as e: self.send(e.status,{'error':e.message})
   return
  files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/route.gpx':'route.gpx'}
  if path not in files: self.send(404,{'error':'Non trovato'});return
  f=ROOT/'web'/files[path];kind={'html':'text/html; charset=utf-8','js':'text/javascript','css':'text/css','gpx':'application/gpx+xml'}[f.suffix[1:]]
  self.send(200,f.read_bytes(),kind)
 def do_POST(self):
  try:
   self.check_host();self.check_origin()
   # Browser fetch must provide a non-simple custom header; no CORS enabled.
   if self.headers.get('X-Europa-Demo')!='1': raise Problem(403,'Richiesta non consentita')
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=8192: raise Problem(413,'Dimensione richiesta non valida')
   b=json.loads(self.rfile.read(n))
   if not isinstance(b,dict): raise Problem(400,'Oggetto JSON richiesto')
   action=self.path.removeprefix('/api/')
   if action=='login':
    s=authenticate(b.get('username'),b.get('password'),self.client_address[0])
    with AUTH_LOCK:
     for old in list(SESSIONS):
      if SESSIONS[old]['expires']<=time.time(): del SESSIONS[old]
     cookie=SimpleCookie(self.headers.get('Cookie',''));old=cookie.get('europa_session')
     if old: SESSIONS.pop(old.value,None)
     if len(SESSIONS)>=MAX_SESSIONS: raise Problem(429,'Troppe sessioni')
     sid=secrets.token_urlsafe(32);s.update(csrf=secrets.token_urlsafe(24),expires=time.time()+SESSION_TTL);SESSIONS[sid]=s
    self.send(200,s,cookie='europa_session='+sid+'; HttpOnly; SameSite=Strict; Path=/; Max-Age='+str(SESSION_TTL));return
   s=self.session()
   if self.headers.get('X-CSRF-Token')!=s['csrf']: raise Problem(403,'CSRF non valido')
   if action=='logout':
    cookie=SimpleCookie(self.headers.get('Cookie',''))
    with AUTH_LOCK: SESSIONS.pop(cookie['europa_session'].value,None)
    self.send(200,{'logged_out':True},cookie='europa_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0');return
   self.send(200,operate(s,action,b))
  except Problem as e: self.send(e.status,{'error':e.message})
  except (ValueError,TypeError,json.JSONDecodeError): self.send(400,{'error':'Richiesta non valida'})
 def log_message(self,*args): pass
def make_server(host,port):
 check_runtime(os.environ.get('EUROPA_MODE','demo'),host)
 http=ThreadingHTTPServer((host,port),Handler)
 http.allowed_hosts={f'{h}:{http.server_port}' for h in ('localhost','127.0.0.1')}
 return http

if __name__=='__main__':
 parser=argparse.ArgumentParser(description='Europa: ambiente di prova autenticato, non utilizzabile in produzione')
 parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','3000')))
 parser.add_argument('--host',default='127.0.0.1',choices=['127.0.0.1','localhost'])
 account_action=parser.add_mutually_exclusive_group()
 account_action.add_argument('--create-user')
 account_action.add_argument('--disable-user')
 parser.add_argument('--role',choices=sorted(ROLES),default='participant')
 parser.add_argument('--tenant',choices=['club-demo','club-other'],default='club-demo')
 args=parser.parse_args()
 check_runtime(os.environ.get('EUROPA_MODE','demo'),args.host)
 init()
 if args.disable_user:
  with connect() as c:
   result=c.execute('UPDATE users SET active=0 WHERE username=?',(args.disable_user,))
   if result.rowcount!=1: parser.error('Account non trovato')
 elif args.create_user:
  password=getpass.getpass('Password (almeno 12 caratteri): ')
  if password!=getpass.getpass('Ripeti password: '): parser.error('Password diverse')
  create_user(args.create_user,password,args.role,args.tenant)
 else:
  http=make_server(args.host,args.port)
  print(f'Europa demo autenticata http://{args.host}:{http.server_port}',flush=True)
  http.serve_forever()
