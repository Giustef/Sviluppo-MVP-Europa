'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
function sandbox(shared={data:new Map(),tail:Promise.resolve()}){
 const locks={request:(_key,fn)=>{const p=shared.tail.then(fn);shared.tail=p.catch(()=>{});return p}};
 const context={localStorage:{getItem:k=>shared.data.get(k)||null,setItem:(k,v)=>shared.data.set(k,v),removeItem:k=>shared.data.delete(k)},crypto:webcrypto,window:{fetch:()=>{throw Error('No external API')}},location:{href:'https://demo.test',origin:'https://demo.test'},URL,Response,navigator:{onLine:true,locks}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('dist/demo-api.js','utf8'),context);
 const op=(a,b={})=>vm.runInContext(`demoOperation(${JSON.stringify(a)},${JSON.stringify(b)})`,context);
 const request=async(a,b={})=>{const r=await context.window.fetch('/api/'+a,{body:JSON.stringify(b)});return {ok:r.ok,data:await r.json()}};
 return {context,op,request,shared};
}
(async()=>{
 const {op}=sandbox();let r=op('register',{name:'Alex Demo',meal:true,key:'registration-1'});
 assert.equal(r.state,'requested');assert.equal(r.token,null);
 assert.throws(()=>op('pay',{id:r.id,success:true}));assert.throws(()=>op('approve',{id:r.id}));
 op('login',{role:'admin'});op('approve',{id:r.id});op('login',{role:'participant'});
 op('pay',{id:r.id,success:true});r=op('state').registrations[0];assert(r.token);
 op('login',{role:'staff'});op('scan',{token:r.token,service:'meal'});assert.throws(()=>op('scan',{token:r.token,service:'meal'}));
 assert.equal(op('state').totals.consumed,1);
 op('login',{role:'restaurant'});assert.equal(op('state').registrations.length,0);assert.equal(op('state').incidents.length,0);assert.equal(op('state').totals.amount,null);assert.throws(()=>op('approve',{id:r.id}));assert.throws(()=>op('sos',{key:'sos-key-1'}));assert.throws(()=>op('scan',{token:r.token,service:'event'}));
 const s=sandbox();for(let i=0;i<45;i++){s.op('login',{role:'participant'});r=s.op('register',{name:'Rejected Demo',meal:false,key:'rejected-'+i});s.op('login',{role:'admin'});s.op('reject',{id:r.id});}
 s.op('login',{role:'participant'});r=s.op('register',{name:'Still works',meal:false,key:'still-works'});s.op('login',{role:'admin'});assert.equal(s.op('approve',{id:r.id}).state,'held');
 const e=sandbox();r=e.op('register',{name:'Expired Demo',meal:true,key:'expires-key'});e.op('login',{role:'admin'});e.op('approve',{id:r.id});let data=JSON.parse(e.shared.data.get('europa-web-v2'));data.registrations[0].expires=0;e.shared.data.set('europa-web-v2',JSON.stringify(data));assert.throws(()=>e.op('pay',{id:r.id,success:true}));assert.equal(e.op('state').registrations[0].state,'expired');
 e.op('login',{role:'participant'});const sos=e.op('sos',{key:'sos-key-123',message:'Help demo'});assert.equal(e.op('sos',{key:'sos-key-123'}).id,sos.id);e.op('login',{role:'staff'});assert.throws(()=>e.op('close',{id:sos.id,reason:'Closing'}));e.op('ack',{id:sos.id});e.op('login',{role:'admin'});e.op('close',{id:sos.id,reason:'Closed demo'});const closed=e.op('state').incidents[0];assert.equal(closed.assignee,'staff');assert.equal(closed.closed_by,'admin');assert.equal(closed.reason,'Closed demo');
 // Two independently loaded tabs share storage and the same lock manager.
 const shared={data:new Map(),tail:Promise.resolve()},a=sandbox(shared),b=sandbox(shared);
 await a.request('login',{role:'admin'});await b.request('login',{role:'admin'});
 const ids=[];for(let i=0;i<41;i++)ids.push((await a.request('register',{name:'Concurrent Demo',meal:false,key:'concurrent-'+i})).data.id);
 const approvals=await Promise.all(ids.map((id,i)=>(i%2?a:b).request('approve',{id})));
 assert.equal(approvals.filter(x=>x.ok).length,40);
 await a.request('pay',{id:ids[0],success:true});const token=(await a.request('state')).data.registrations.find(r=>r.id===ids[0]).token;
 const scans=await Promise.all([a.request('scan',{token,service:'event'}),b.request('scan',{token,service:'event'})]);assert.equal(scans.filter(x=>x.ok).length,1);
 a.context.navigator.onLine=false;assert.equal((await a.request('sos',{key:'offline-sos'})).ok,false);
 a.context.navigator.onLine=true;a.context.navigator.locks=null;assert.equal((await a.request('pay',{id:ids[1],success:true})).ok,false);
 assert.equal(fs.readFileSync('web/app.js','utf8'),fs.readFileSync('dist/app.js','utf8'));
 assert(!fs.readFileSync('web/index.html','utf8').includes('id="role"'));
 console.log('Web regression checks passed: approval, roles, QR pool, expiry, SOS, two-tab capacity/scan locking, offline, fail-closed locks, UI parity.');
})().catch(e=>{console.error(e);process.exitCode=1});
