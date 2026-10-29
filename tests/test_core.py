import concurrent.futures, json, tempfile, unittest, sys, sqlite3, threading, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server as app
class Base(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();app.DB=str(Path(self.tmp.name)/'test.db');app.init()
  self.p={'user':'participant-a','tenant':'club-demo','role':'participant'}
  self.staff={'user':'staff-a','tenant':'club-demo','role':'staff'}
  self.admin={'user':'admin-a','tenant':'club-demo','role':'admin'}
  app.SESSIONS.clear();app.LOGIN_ATTEMPTS.clear()
 def tearDown(self): self.tmp.cleanup()
 def reg(self,key='abcdefgh',meal=True): return app.operate(self.p,'register',{'name':'Alex Demo','key':key,'meal':meal})
 def approved(self,key='abcdefgh',meal=True):
  r=self.reg(key,meal);app.operate(self.admin,'approve',{'id':r['id']});return r
 def paid(self):
  r=self.approved();app.operate(self.p,'pay',{'id':r['id'],'success':True});return r
 def problem(self,status,fn):
  with self.assertRaises(app.Problem) as ctx: fn()
  self.assertEqual(ctx.exception.status,status)
class Core(Base):
 def test_registration_idempotency(self): self.assertEqual(self.reg()['id'],self.reg()['id'])
 def test_payment_idempotency(self):
  r=self.paid();app.operate(self.p,'pay',{'id':r['id'],'success':True})
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM payments').fetchone()[0],1)
 def test_failed_payment_no_pass(self):
  r=self.approved();app.operate(self.p,'pay',{'id':r['id'],'success':False})
  self.problem(400,lambda:app.operate(self.staff,'scan',{'token':r['token']}))
 def test_duplicate_meal(self):
  r=self.paid();app.operate(self.staff,'scan',{'token':r['token']})
  self.problem(409,lambda:app.operate(self.staff,'scan',{'token':r['token']}))
  self.assertEqual(app.operate(self.staff,'state',{})['totals']['consumed'],1)
 def test_tenant_isolation(self): self.problem(404,lambda:app.operate({**self.staff,'tenant':'club-other'},'state',{'event_id':'salento'}))
 def test_participant_cannot_scan(self):self.problem(403,lambda:app.operate(self.p,'scan',{'token':'x'}))
 def test_restaurant_no_identities_or_finance(self):
  self.paid();s=app.operate({**self.staff,'role':'restaurant'},'state',{})
  self.assertEqual(s['registrations'],[]);self.assertIsNone(s['totals']['amount'])
 def test_last_place_concurrent(self):
  with app.connect() as c:c.execute("UPDATE events SET capacity=1 WHERE id='salento'")
  def run(i):
   try:self.approved('concurrent-'+str(i));return True
   except app.Problem:return False
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(sum(pool.map(run,range(8))),1)
 def test_expired_hold_frees_place(self):
  r=self.approved()
  with app.connect() as c:
   c.execute("UPDATE events SET capacity=1 WHERE id='salento'");c.execute('UPDATE registrations SET expires=0 WHERE id=?',(r['id'],))
  self.approved('new-valid-key');self.problem(409,lambda:app.operate(self.p,'pay',{'id':r['id'],'success':True}))
 def test_sos_notification_idempotency_and_states(self):
  b={'key':'sos-test-key','message':'Test demo'};r=app.operate(self.p,'sos',b)
  self.assertEqual(r['id'],app.operate(self.p,'sos',b)['id'])
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM notifications').fetchone()[0],1)
  self.problem(409,lambda:app.operate(self.staff,'close',{'id':r['id'],'reason':'Concluso'}))
  app.operate(self.staff,'ack',{'id':r['id']});app.operate(self.staff,'close',{'id':r['id'],'reason':'Simulazione conclusa'})
  self.assertEqual(app.operate(self.staff,'state',{})['incidents'][0]['state'],'closed')
  self.assertFalse(r['public_emergency_services_contacted'])
 def test_sos_gps_validation(self):self.problem(400,lambda:app.operate(self.p,'sos',{'key':'abcdefgh','lat':100,'lon':20}))
 def test_sos_restricted(self):self.problem(403,lambda:app.operate({**self.staff,'role':'restaurant'},'sos',{'key':'abcdefgh'}))
 def test_audit_immutable(self):
  self.reg()
  with app.connect() as c:
   with self.assertRaises(sqlite3.IntegrityError):c.execute('DELETE FROM audit')
 def test_112_only_manual(self):
  js=(app.ROOT/'web/app.js').read_text();html=(app.ROOT/'web/index.html').read_text()
  self.assertEqual(js.count('href="tel:112"'),1)
  for forbidden in ['location.href','window.open','tel:112)']:self.assertNotIn(forbidden,js)
  self.assertNotIn('tel:',(app.ROOT/'server.py').read_text());self.assertIn('3000',js)
 def test_qr_svg_real(self):
  import qrcode,qrcode.image.svg,io
  out=io.BytesIO();qrcode.make(self.paid()['token'],image_factory=qrcode.image.svg.SvgPathImage).save(out)
  self.assertIn(b'<svg',out.getvalue())
 def test_individual_passes(self):self.assertNotEqual(self.reg()['token'],self.reg('second-person')['token'])
class HTTP(Base):
 def test_http_auth_csrf_and_headers(self):
  app.create_user('staff-test','test-password-123','staff','club-demo')
  http=app.make_server('127.0.0.1',0);t=threading.Thread(target=http.serve_forever,daemon=True);t.start();url='http://127.0.0.1:'+str(http.server_port)
  try:
   with urllib.request.urlopen(url+'/') as r:self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url+'/api/state')
   self.assertEqual(e.exception.code,401)
   req=urllib.request.Request(url+'/api/login',data=b'{"username":"staff-test","password":"test-password-123"}',headers={'Content-Type':'application/json','X-Europa-Demo':'1'})
   with urllib.request.urlopen(req) as r:cookie=r.headers['Set-Cookie'];s=json.load(r)
   req=urllib.request.Request(url+'/api/ack',data=b'{}',headers={'Content-Type':'application/json','X-Europa-Demo':'1','Cookie':cookie})
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
   self.assertEqual(e.exception.code,403)
  finally:http.shutdown();http.server_close();t.join()
if __name__=='__main__':unittest.main()

