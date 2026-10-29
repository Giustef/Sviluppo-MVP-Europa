import concurrent.futures
import http.client
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from test_core import Base
import server as app

class Isolation(Base):
 def test_approval_required_and_role_enforced(self):
  r=self.reg()
  self.assertEqual(r['state'],'requested')
  self.problem(409,lambda:app.operate(self.p,'pay',{'id':r['id'],'success':True}))
  for role in ('participant','staff','restaurant'):
   self.problem(403,lambda:app.operate({**self.p,'role':role},'approve',{'id':r['id']}))
  app.operate(self.admin,'approve',{'id':r['id']})
  app.operate(self.p,'pay',{'id':r['id'],'success':True})
  self.assertEqual(app.operate(self.p,'state',{})['registrations'][0]['state'],'paid')
 def test_rejected_registration_never_payable(self):
  r=self.reg();app.operate(self.admin,'reject',{'id':r['id']})
  self.problem(409,lambda:app.operate(self.p,'pay',{'id':r['id'],'success':True}))
  self.problem(409,lambda:app.operate(self.admin,'approve',{'id':r['id']}))
 def test_two_users_have_separate_registrations_and_payments(self):
  r=self.approved();other={**self.p,'user':'participant-b'}
  self.assertEqual(app.operate(other,'state',{})['registrations'],[])
  self.problem(404,lambda:app.operate(other,'pay',{'id':r['id'],'success':True}))
  r2=app.operate(other,'register',{'key':'abcdefgh','name':'Other Demo','meal':True})
  self.assertNotEqual(r['id'],r2['id'])
 def test_staff_has_no_pass_tokens_or_finance_records(self):
  self.paid();state=app.operate(self.staff,'state',{})
  self.assertEqual(state['registrations'],[]);self.assertIsNone(state['totals']['amount'])
 def test_sos_idempotency_is_event_and_actor_scoped(self):
  b={'key':'same-key-123','message':'Private A'};a=app.operate(self.p,'sos',b)
  other={**self.p,'tenant':'club-other'}
  b2=app.operate(other,'sos',{**b,'event_id':'other','message':'Private B'})
  self.assertNotEqual(a['id'],b2['id'])
  self.assertEqual(app.operate(other,'sos',{**b,'event_id':'other'})['message'],'Private B')
  self.assertEqual(app.operate(self.p,'state',{})['incidents'][0]['message'],'Private A')
  c=app.operate({**self.p,'user':'participant-b'},'sos',b)
  self.assertNotEqual(a['id'],c['id'])
 def test_state_never_expires_other_tenant(self):
  other={**self.p,'tenant':'club-other'}
  r=app.operate(other,'register',{'event_id':'other','key':'register-other','name':'Other Demo','meal':False})
  app.operate({**self.admin,'tenant':'club-other'},'approve',{'event_id':'other','id':r['id']})
  with app.connect() as c:c.execute('UPDATE registrations SET expires=0 WHERE id=?',(r['id'],))
  app.operate(self.p,'state',{})
  with app.connect() as c:self.assertEqual(c.execute('SELECT state FROM registrations WHERE id=?',(r['id'],)).fetchone()[0],'held')
 def test_sos_closer_preserves_assignee_and_reason(self):
  r=app.operate(self.p,'sos',{'key':'sos-close-key'})
  app.operate(self.staff,'ack',{'id':r['id']})
  self.problem(403,lambda:app.operate({**self.staff,'user':'staff-b'},'close',{'id':r['id'],'reason':'Close demo'}))
  app.operate(self.admin,'close',{'id':r['id'],'reason':'Closed by administrator'})
  i=app.operate(self.staff,'state',{})['incidents'][0]
  self.assertEqual(i['assignee'],self.staff['user']);self.assertEqual(i['closed_by'],self.admin['user'])
  self.assertEqual(i['close_reason'],'Closed by administrator');self.assertIsNotNone(i['closed_at'])
 def test_other_tenant_cannot_approve_scan_or_close(self):
  r=self.paid();i=app.operate(self.p,'sos',{'key':'sos-tenant-key'})
  other={**self.admin,'tenant':'club-other'}
  self.problem(409,lambda:app.operate(other,'approve',{'id':r['id']}))
  self.problem(400,lambda:app.operate(other,'scan',{'token':r['token']}))
  self.problem(404,lambda:app.operate(other,'ack',{'id':i['id']}))
 def test_meal_capacity_is_enforced_at_approval(self):
  with app.connect() as c:c.execute("UPDATE events SET meal_capacity=1 WHERE id='salento'")
  self.approved();r=self.reg('second-meal')
  self.problem(409,lambda:app.operate(self.admin,'approve',{'id':r['id']}))
  self.approved('no-meal-key',False)
 def test_legacy_database_is_refused_without_modification(self):
  with tempfile.TemporaryDirectory() as d:
   old=str(Path(d)/'legacy.db')
   with sqlite3.connect(old) as c:c.execute('CREATE TABLE registrations(id TEXT)')
   with patch.object(app,'DB',old):
    with self.assertRaises(RuntimeError):app.init()
   with sqlite3.connect(old) as c:self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='users'").fetchone())
 def test_runtime_refuses_production_and_network_bind(self):
  for mode,host in [('production','127.0.0.1'),('demo','0.0.0.0'),('demo','192.168.1.1')]:
   with self.assertRaises(RuntimeError):app.check_runtime(mode,host)
  app.check_runtime('demo','127.0.0.1')

class AuthHTTP(Base):
 def setUp(self):
  super().setUp()
  for username,role in [('alice','participant'),('bob','participant'),('admin-test','admin')]:
   app.create_user(username,'test-password-123',role,'club-demo')
  self.http=app.make_server('127.0.0.1',0)
  self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):
  self.http.shutdown();self.http.server_close();self.thread.join();super().tearDown()
 def request(self,path,body=None,cookie=None,csrf=None,headers=None):
  conn=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
  h={'X-Europa-Demo':'1','Content-Type':'application/json'}
  if cookie:h['Cookie']=cookie
  if csrf:h['X-CSRF-Token']=csrf
  h.update(headers or {})
  conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h)
  r=conn.getresponse();raw=r.read();out=(r.status,dict(r.getheaders()),json.loads(raw) if r.getheader('Content-Type')=='application/json' else raw);conn.close();return out
 def login(self,name='alice'):
  status,h,s=self.request('/api/login',{'username':name,'password':'test-password-123','role':'admin','tenant':'club-other'})
  self.assertEqual(status,200)
  return h['Set-Cookie'].split(';')[0],s
 def test_public_role_selection_is_rejected(self):
  self.assertEqual(self.request('/api/login',{'role':'admin'})[0],401)
  cookie,s=self.login();self.assertEqual(s['role'],'participant');self.assertEqual(s['tenant'],'club-demo')
  self.assertEqual(self.request('/api/approve',{'id':'x'},cookie,s['csrf'])[0],403)
 def test_real_accounts_have_distinct_identity_and_private_qr(self):
  ca,a=self.login();cb,b=self.login('bob');cc,admin=self.login('admin-test')
  self.assertNotEqual(a['user'],b['user'])
  status,_,reg=self.request('/api/register',{'name':'Alice Demo','meal':True,'key':'http-reg-key'},ca,a['csrf']);self.assertEqual(status,200)
  self.assertEqual(self.request('/api/approve',{'id':reg['id']},cc,admin['csrf'])[0],200)
  self.assertEqual(self.request('/api/pay',{'id':reg['id'],'success':True},ca,a['csrf'])[0],200)
  self.assertEqual(self.request('/api/state',cookie=cb)[2]['registrations'],[])
  self.assertEqual(self.request('/api/qr/'+reg['id'],cookie=cb)[0],404)
  self.assertEqual(self.request('/api/qr/'+reg['id'],cookie=ca)[0],200)
 def test_csrf_origin_and_host_are_enforced(self):
  cookie,s=self.login()
  self.assertEqual(self.request('/api/sos',{'key':'sos-http-key'},cookie)[0],403)
  self.assertEqual(self.request('/api/sos',{'key':'sos-http-key'},cookie,s['csrf'],{'Origin':'https://evil.test'})[0],403)
  self.assertEqual(self.request('/api/state',cookie=cookie,headers={'Host':'evil.test'})[0],403)
  self.assertEqual(self.request('/api/login',{'username':'alice','password':'test-password-123'},headers={'Origin':'null'})[0],403)
 def test_session_expiry_logout_rotation_and_deactivation(self):
  cookie,s=self.login();self.assertIn('HttpOnly',self.request('/api/login',{'username':'alice','password':'test-password-123'})[1]['Set-Cookie'])
  status,h,new=self.request('/api/login',{'username':'alice','password':'test-password-123'},cookie)
  self.assertEqual(self.request('/api/state',cookie=cookie)[0],401)
  cookie=h['Set-Cookie'].split(';')[0]
  self.assertEqual(self.request('/api/logout',{},cookie,new['csrf'])[0],200)
  self.assertEqual(self.request('/api/state',cookie=cookie)[0],401)
  cookie,s=self.login();app.SESSIONS[cookie.split('=',1)[1]]['expires']=0
  self.assertEqual(self.request('/api/state',cookie=cookie)[0],401)
  cookie,s=self.login()
  with app.connect() as c:c.execute('UPDATE users SET active=0 WHERE id=?',(s['user'],))
  self.assertEqual(self.request('/api/state',cookie=cookie)[0],401)
 def test_password_storage_and_bruteforce_limit(self):
  with app.connect() as c:stored=c.execute("SELECT password_hash FROM users WHERE username='alice'").fetchone()[0]
  self.assertNotIn('test-password-123',stored)
  for _ in range(10):self.assertEqual(self.request('/api/login',{'username':'alice','password':'wrong'})[0],401)
  self.assertEqual(self.request('/api/login',{'username':'alice','password':'wrong'})[0],429)

if __name__=='__main__':unittest.main()
