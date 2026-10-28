"""Demo locale: nessuna credenziale reale, nessun invio esterno. Python >=3.11."""
import json, os, secrets, sqlite3, time, uuid, sys, io
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'vendor'))
DB=os.environ.get('EUROPA_DB',str(ROOT/'demo.sqlite3'))
SESSIONS={}
ROLES={'participant','staff','organizer','restaurant','admin'}
class Problem(Exception):
 def __init__(self,status,message): self.status,self.message=status,message

def connect():
 c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init():
 with connect() as c: c.executescript((ROOT/'schema.sql').read_text())

def audit(c,s,action,entity): c.execute('INSERT INTO audit(actor,action,entity,created) VALUES(?,?,?,?)',(s['user'],action,entity,time.time()))

def require(s,roles):
 if s['role'] not in roles: raise Problem(403,'Ruolo non autorizzato')

def event(c,s,eid):
 r=c.execute('SELECT * FROM events WHERE id=? AND tenant=?',(eid,s['tenant'])).fetchone()
 if not r: raise Problem(404,'Evento non disponibile')
 return dict(r)

def operate(s,action,b):
 if action=='me': return s
 eid=b.get('event_id','salento')
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  e=event(c,s,eid)
  c.execute("UPDATE registrations SET state='expired' WHERE state='held' AND expires<?",(time.time(),))
  if action=='state':
   regs=[dict(x) for x in c.execute('SELECT * FROM registrations WHERE event_id=?',(eid,))]
   own=[r for r in regs if r['idem'].startswith(s['user']+':')]
   if s['role']=='participant': regs=own
   if s['role']=='restaurant': regs=[]
   incidents=[]
   if s['role'] in {'staff','organizer','admin'}: incidents=[dict(x) for x in c.execute('SELECT * FROM incidents WHERE event_id=? ORDER BY created DESC',(eid,))]
   elif s['role']=='participant': incidents=[dict(x) for x in c.execute('SELECT * FROM incidents WHERE event_id=? AND actor=?',(eid,s['user']))]
   paid=c.execute("SELECT COUNT(*) n,COALESCE(SUM(amount),0) amount,COALESCE(SUM(meal),0) meals FROM registrations WHERE event_id=? AND state='paid'",(eid,)).fetchone()
   meals=c.execute("SELECT COUNT(*) FROM scans s JOIN registrations r ON r.id=s.registration_id WHERE r.event_id=? AND service='meal'",(eid,)).fetchone()[0]
   return {'event':e,'registrations':regs,'incidents':incidents,'totals':{'paid':paid['n'],'amount':paid['amount'] if s['role'] in {'organizer','admin'} else None,'booked_meals':paid['meals'],'consumed':meals},'demo':True}
  if action=='register':
   require(s,{'participant','organizer','admin'})
   name=str(b.get('name','')).strip(); key=str(b.get('key',''))
   if not 2<=len(name)<=100 or not 8<=len(key)<=100 or type(b.get('meal')) is not bool: raise Problem(400,'Nome, opzione pasto o chiave non validi')
   idem=s['user']+':'+key
   old=c.execute('SELECT * FROM registrations WHERE event_id=? AND idem=?',(eid,idem)).fetchone()
   if old: return dict(old)
   used=c.execute("SELECT COUNT(*),COALESCE(SUM(meal),0) FROM registrations WHERE event_id=? AND state IN ('held','paid')",(eid,)).fetchone()
   if used[0]>=e['capacity'] or b['meal'] and used[1]>=e['meal_capacity']: raise Problem(409,'Capienza esaurita')
   rid=uuid.uuid4().hex
   c.execute('INSERT INTO registrations VALUES(?,?,?,?,?,?,?,?,?)',(rid,eid,name,int(b['meal']),'held',time.time()+600,e['price'] if b['meal'] else 1500,secrets.token_urlsafe(32),idem))
   audit(c,s,'registration.held',rid)
   return dict(c.execute('SELECT * FROM registrations WHERE id=?',(rid,)).fetchone())
  if action=='pay':
   require(s,{'participant','organizer','admin'})
   r=c.execute('SELECT * FROM registrations WHERE id=? AND event_id=?',(b.get('id'),eid)).fetchone()
   if not r or s['role']=='participant' and not r['idem'].startswith(s['user']+':'): raise Problem(404,'Iscrizione non disponibile')
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
   key=str(b.get('key',''))
   if not 8<=len(key)<=100: raise Problem(400,'Chiave richiesta')
   lat,lon,acc=b.get('lat'),b.get('lon'),b.get('accuracy')
   if (lat is None)!=(lon is None): raise Problem(400,'Coordinate incomplete')
   if lat is not None and (type(lat) not in (float,int) or type(lon) not in (float,int) or not -90<=lat<=90 or not -180<=lon<=180): raise Problem(400,'Coordinate non valide')
   if acc is not None and (type(acc) not in (float,int) or not 0<=acc<=100000): raise Problem(400,'Accuratezza non valida')
   idem=s['user']+':'+key
   old=c.execute('SELECT * FROM incidents WHERE idem=?',(idem,)).fetchone()
   if old: return dict(old)
   iid=uuid.uuid4().hex
   c.execute('INSERT INTO incidents VALUES(?,?,?,?,?,?,?,?,?,?,?)',(iid,eid,s['user'],str(b.get('message','Richiesta assistenza demo'))[:500],lat,lon,acc,'received',None,time.time(),idem))
   c.execute('INSERT INTO notifications(id,incident_id) VALUES(?,?)',(uuid.uuid4().hex,iid));audit(c,s,'sos.received',iid)
   return {'id':iid,'state':'received','notification':'available_in_staff_demo_inbox','public_emergency_services_contacted':False}
  if action in {'ack','close'}:
   require(s,{'staff','organizer','admin'})
   r=c.execute('SELECT * FROM incidents WHERE id=? AND event_id=?',(b.get('id'),eid)).fetchone()
   if not r: raise Problem(404,'SOS non disponibile')
   if action=='close' and (r['state']!='acknowledged' or len(str(b.get('reason','')).strip())<5): raise Problem(409,'Prima prendere in carico e indicare una motivazione')
   if action=='ack' and r['state']!='received': raise Problem(409,'SOS già assegnato o chiuso')
   state='acknowledged' if action=='ack' else 'closed'
   c.execute('UPDATE incidents SET state=?,assignee=? WHERE id=?',(state,s['user'],r['id']));audit(c,s,'sos.'+state+':'+str(b.get('reason',''))[:200],r['id']);return {'state':state}
  raise Problem(404,'Operazione sconosciuta')

class Handler(BaseHTTPRequestHandler):
 def send(self,status,data,kind='application/json',cookie=None):
  raw=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
  if cookie: self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(raw)
 def session(self):
  cookie=SimpleCookie(self.headers.get('Cookie',''));sid=cookie.get('europa_session');s=SESSIONS.get(sid.value if sid else '')
  if not s: raise Problem(401,'Seleziona un profilo demo')
  return s
 def do_GET(self):
  path=self.path.split('?')[0]
  if path.startswith('/api/qr/'):
   try:
    import qrcode, qrcode.image.svg
    s=self.session();rid=path.rsplit('/',1)[-1]
    with connect() as c:
     r=c.execute("SELECT r.* FROM registrations r JOIN events e ON e.id=r.event_id WHERE r.id=? AND e.tenant=? AND r.state='paid'",(rid,s['tenant'])).fetchone()
     if not r or s['role']=='restaurant' or s['role']=='participant' and not r['idem'].startswith(s['user']+':'): raise Problem(404,'Pass non disponibile')
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
   # Browser fetch must provide a non-simple custom header; no CORS enabled.
   if self.headers.get('X-Europa-Demo')!='1': raise Problem(403,'Richiesta non consentita')
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=8192: raise Problem(413,'Dimensione richiesta non valida')
   b=json.loads(self.rfile.read(n))
   if not isinstance(b,dict): raise Problem(400,'Oggetto JSON richiesto')
   action=self.path.removeprefix('/api/')
   if action=='login':
    role=b.get('role');tenant=b.get('tenant','club-demo')
    if role not in ROLES or tenant not in {'club-demo','club-other'}: raise Problem(400,'Profilo demo sconosciuto')
    sid=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
    s={'user':role+'-demo','role':role,'tenant':tenant,'csrf':csrf};SESSIONS[sid]=s
    self.send(200,s,cookie='europa_session='+sid+'; HttpOnly; SameSite=Strict; Path=/');return
   s=self.session()
   if self.headers.get('X-CSRF-Token')!=s['csrf']: raise Problem(403,'CSRF non valido')
   self.send(200,operate(s,action,b))
  except Problem as e: self.send(e.status,{'error':e.message})
  except (ValueError,TypeError,json.JSONDecodeError): self.send(400,{'error':'Richiesta non valida'})
 def log_message(self,*args): pass
if __name__=='__main__':
 init();port=int(sys.argv[sys.argv.index('--port')+1]) if '--port' in sys.argv else int(os.environ.get('PORT','3000'));print(f'Europa demo http://localhost:{port}',flush=True);ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
