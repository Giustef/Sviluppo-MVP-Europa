'use strict';
// Dependency-free execution of the real UI handlers with a minimal DOM adapter.
// This does not replace a browser layout/accessibility test.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const elements=new Map();const element=()=>({hidden:false,value:'',textContent:'',innerHTML:'',replaceChildren(){this.innerHTML=''},showModal(){},close(){},setPointerCapture(){}});
for(const id of ['auth','auth-form','username','password','logout','account','notice','content','pay-ok','pay-fail','pay-cancel','payment'])elements.set('#'+id,element());
let scheduled,bodyHistory=[],failSos=false,unauthorized=false;
let serverState={event:{title:'Test Demo',capacity:40,meal_capacity:30},totals:{paid:0,booked_meals:0,consumed:0,amount:null},registrations:[],incidents:[]};
const c={window:{},document:{querySelector:s=>elements.get(s)||null,querySelectorAll:()=>[]},crypto:webcrypto,Intl,Date,JSON,String,URL,Blob,Response,navigator:{onLine:true},localStorage:{getItem:()=>JSON.stringify({version:'<img src=x onerror=alert(1)>',stops:[['Safe','Safe','Safe','Safe']]})},setInterval(){},clearTimeout(){},setTimeout(fn){scheduled=fn;return 1},fetch:async(path,init)=>{const action=path.slice(5),body=init?.body?JSON.parse(init.body):null;if(body)bodyHistory.push({action,body});if(action==='sos'&&failSos)throw Error('Reply lost');if(action==='login')return Response.json({role:'participant',user:'alice-id',csrf:'csrf-fixture'});if(unauthorized)return Response.json({error:'expired'},{status:401});return Response.json(action==='state'?serverState:{});}};
vm.createContext(c);vm.runInContext(fs.readFileSync('web/app.js','utf8'),c);
(async()=>{
 elements.get('#username').value='alice';elements.get('#password').value='test-password-123';
 await vm.runInContext('login()',c);
 const login=bodyHistory.find(x=>x.action==='login').body;
 assert.equal(login.username,'alice');assert.equal(login.password,'test-password-123');assert(!('role' in login));assert.equal(elements.get('#password').value,'');assert.equal(elements.get('#auth').hidden,true);
 vm.runInContext("tab='route';navigator.onLine=false;render()",c);
 assert(elements.get('#content').innerHTML.includes('&lt;img src=x onerror=alert(1)&gt;'));assert(!elements.get('#content').innerHTML.includes('<img src=x onerror='));
 c.navigator.onLine=true;
 for(const id of ['hold-sos','sos-message','sos-status'])elements.set('#'+id,element());
 elements.get('#sos-message').value='SOS demo';vm.runInContext("tab='sos';render()",c);
 const hold=elements.get('#hold-sos');failSos=true;
 hold.onpointerdown({pointerId:1});await scheduled();
 assert(elements.get('#sos-status').textContent.includes('NON CONFERMATO'));
 hold.onpointerdown({pointerId:1});await scheduled();
 const sent=bodyHistory.filter(x=>x.action==='sos');assert.equal(sent.length,2);assert.equal(sent[0].body.key,sent[1].body.key);
 c.navigator.onLine=false;hold.onpointerdown({pointerId:1});await scheduled();assert(elements.get('#sos-status').textContent.includes('NON INVIATO'));assert.equal(bodyHistory.filter(x=>x.action==='sos').length,2);
 c.navigator.onLine=true;unauthorized=true;await vm.runInContext('refresh()',c);
 assert.equal(vm.runInContext('session',c),null);assert.equal(elements.get('#content').innerHTML,'');assert.equal(elements.get('#auth').hidden,false);
 console.log('UI handler checks passed: credential-only login, password clearing, cache escaping, ambiguous SOS retry idempotency, offline state, expired-session clearing.');
})().catch(e=>{console.error(e);process.exitCode=1});
