const DEMO_TOKENS=["HpanxurotW7OpxE8PQ8kbOyHYI8-vassYU_9vsoESmE", "IeJYmSSMFZMxg1IaCUdhP79heLTPk376RSs_9Lrm88g", "AQq266vnce53sqJr6ms85cjL1CJEUbdqlZgIEicNtgo", "Aa--_P14-CqA3pgKdyBlGMoBTgsHe_lkLJHWb5oaeQ0", "w_pnz6Lf1rrUb4UZed8poKV98hXejFikvA-XNcl5p7k", "MB9f7VswZQPnR6qUQcSG3Ng0tza2E72irnoLg4nVHNg", "Y8BDvdg_6e_w4N1bS9E5q3GcSBc9F7rlX3CqeqiGebQ", "nlQSAcbezLZviZS_qHzqsDqb0gTuX3N4vKBz0xN8hTk", "j0szu6NUyUx6OxYtUhGudoOemrHc7yE2-gvfBhAfaDU", "EIcmjbKReLfqf-WT8eafnJ3YHaeGLIlsK3uqWud-Jeo", "UgCVVW7EdH2TdkMYx_M8ioAbxW0GIpifESxVAqMxnSI", "TUdXRM4vJykJTleKKfMIZkvU6kcF-gTaoyCmdU1t1wE", "j0QA1V9EfqwmKQIP1oceRsnsTx9TsTyOuno90AgP4cU", "TyYHkKcfB5p642MF_xxD7B7KIqZou2zqpuZv90rwydA", "mE23NuVmXSLaBxS3wuaDHQj-xPWJUzC5Bx7tLCtsNWM", "LIhQGX3snXbVnoNmyuwlVvJnQfGUMKQUjkfAh_EFeLM", "0KOQpX6QkZHzqtIPdXIdKC9rbGz_JnU9Woy4Nma8RJw", "DDP8KQHP_0_l6qiE-45-BeFNHtmEsEeznO7yh_dT7I4", "gcpia52BqQzuKeiFaP2AuyHf266PzQZZXUtpGFLK1sI", "gRy1OBbwfndN8RWvK6dmHtWRNziEvH7WZ2q0ThjlCos", "A8groUeg42K54nYXu_7qvmg5IBl6DapFpBaqXeOxT58", "V2Wcj1rh_RntS9zOBH2Z9birgmoZQeGGuY_XJN9DlsY", "3HRlc5OpXOb3mym2mCwCCRdNoa_YFMZn4AXl5UDD0RY", "v3B2Oe7tHpJUkQxIoqJGiJjTXrNfwu9K7lKDx0d7moM", "gz79IaUi8ngw09WcWdpdVNN0-TeaQbdVOLBMattmkbY", "gc_w64k8Xj-hXGQs3W5WRUQItfPfsmCKQBQ4oMCmffM", "KVaz1SzgSL4e6Uex3iC0CuCnt87ANGVKuJCYr-4WCRo", "bYpG5pL4ggXhCNOdKjq-Jh8zzyYm5MvSF3M2GOLfDR4", "LT8cTFPdMAWPKBGGq7ZW63r3SxtEnK61LEtAduAicXI", "xMJFr0cmmlBKSzhnfd4SQP8NE-s3PhuZf_VQkXlEfYI", "YmIsfa-HZeOawGFaZkSWFjR4HNIg1Z8olZbtEd4VmXA", "IKCjNP9cHTkbdSYA_6erYiJhjELTr0C9fZ_iKCozwhc", "Vh6DePiVedyRVc-VAN8xjaj6sUNIyQg4thEUqd_Qpsw", "GtItXWcc37M2F1TS4jIEXnqFXmekwVE3ZcQkEroCKOs", "1wbbs9_CLtvOldgc1LJMN7OXhinXr4-4T6xVDhHWk4s", "jdIVYOrfSCM_W8s9gdktydNmGZcJiBkYGUHEkBwTwho", "p0DP4SnpiUoOg6J0QOWF8us0qSanf9XDoC3ZcgrX05s", "k02fldedNVRP1T4u2ZpwdAD8QjwEO53H07sFh81WoKA", "_5YG-1i7J8nLgVCkrwzRqWEd6_ebDBT14HTykRbDkrM", "3W_-rueZLuZISDwK6JorZ3N6ulXovvJ-k6IJl4LxV2c"];
'use strict';
window.EUROPA_STATIC_DEMO=true;
// Hosted demo only: records remain in this browser, no real accounts or payments.
const DEMO_STORE='europa-web-v2';
let demoRole='participant';
const roles=['participant','staff','organizer','restaurant','admin'];
function loadDemo(){const raw=localStorage.getItem(DEMO_STORE);if(!raw)return {registrations:[],incidents:[],scans:[]};let d;try{d=JSON.parse(raw)}catch{throw Error('Dati demo danneggiati: usa Azzera dati di prova')};if(!d||!['registrations','incidents','scans'].every(k=>Array.isArray(d[k])))throw Error('Formato demo non valido: usa Azzera dati di prova');return d}
function validKey(k){if(typeof k!=='string'||k.length<8||k.length>100)throw Error('Chiave richiesta non valida')}
async function demoLocked(fn){if(!navigator.locks)throw Error('Browser senza Web Locks: usa un browser aggiornato su HTTPS o localhost');return navigator.locks.request('europa-web-v2',fn)}
window.europaResetDemo=()=>demoLocked(()=>{localStorage.removeItem(DEMO_STORE);localStorage.removeItem('europa-web-v1')});
function demoOperation(action,b={}){
 const d=loadDemo(),now=Date.now()/1000,user='demo-participant';
 const fail=t=>{throw Error(t)},requireRole=rs=>{if(!rs.includes(demoRole))fail('Ruolo non autorizzato')};
 d.registrations.forEach(r=>{if(r.state==='held'&&r.expires<now)r.state='expired'});
 let out;
 if(action==='login'){if(!roles.includes(b.role))fail('Profilo non valido');demoRole=b.role;out={role:demoRole,user,csrf:'browser-demo'}}
 else if(action==='state'){
 const paid=d.registrations.filter(r=>r.state==='paid');
 out={event:{id:'salento',title:'Salento Coast Ride',capacity:40,meal_capacity:30,price:4500},registrations:demoRole==='restaurant'?[]:d.registrations,incidents:['restaurant'].includes(demoRole)?[]:d.incidents,totals:{paid:paid.length,amount:['organizer','admin'].includes(demoRole)?paid.reduce((a,r)=>a+r.amount,0):null,booked_meals:paid.filter(r=>r.meal).length,consumed:d.scans.filter(s=>s.service==='meal').length},demo:true};
 }else if(action==='register'){
 requireRole(['participant','organizer','admin']);
 if(typeof b.name!=='string'||b.name.trim().length<2||b.name.trim().length>100||typeof b.meal!=='boolean')fail('Nome o pasto non validi');
 validKey(b.key);const old=d.registrations.find(r=>r.key===b.key);if(old)return old;
 if(d.registrations.filter(r=>r.state==='requested').length>=1000)fail('Troppe richieste in attesa: completare o rifiutare le prove');
 out={id:Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join(''),name:b.name.trim(),meal:b.meal,state:'requested',amount:b.meal?4500:1500,token:null,qr:null,key:b.key,expires:0};d.registrations.push(out);
 }else if(action==='approve'||action==='reject'){
 requireRole(['organizer','admin']);const r=d.registrations.find(r=>r.id===b.id);if(!r||r.state!=='requested')fail('Richiesta non disponibile');
 if(action==='approve'){const reserved=d.registrations.filter(r=>['paid','held'].includes(r.state));if(reserved.length>=40||(r.meal&&reserved.filter(r=>r.meal).length>=30))fail('Capienza esaurita');const index=DEMO_TOKENS.findIndex(t=>!reserved.some(x=>x.token===t));if(index<0)fail('Nessun pass demo disponibile');r.token=DEMO_TOKENS[index];r.qr=index;r.state='held';r.expires=now+600}else r.state='rejected';out=r;
 }else if(action==='pay'){
 requireRole(['participant','organizer','admin']);if(typeof b.success!=='boolean')fail('Esito simulato booleano richiesto');const r=d.registrations.find(r=>r.id===b.id);if(!r)fail('Iscrizione non disponibile');
 if(r.state==='paid')return {state:'paid',simulated:true};if(r.state!=='held')fail('Pagamento disponibile solo dopo approvazione e prima della scadenza');
 r.state=b.success===true?'paid':'failed';out={state:r.state,simulated:true};
 }else if(action==='scan'){
 requireRole(['staff','restaurant','organizer','admin']);if(!['meal','event'].includes(b.service)||(demoRole==='restaurant'&&b.service!=='meal'))fail('Servizio non autorizzato');
 const r=d.registrations.find(r=>r.token===b.token);if(!r||r.state!=='paid'||b.service==='meal'&&!r.meal)fail('Pass non valido per questo servizio');
 if(d.scans.some(s=>s.id===r.id&&s.service===b.service))fail('Pass già utilizzato: nessun coperto aggiunto');
 d.scans.push({id:r.id,service:b.service});out={accepted:true};
 }else if(action==='sos'){
 requireRole(['participant','staff','organizer','admin']);validKey(b.key);
 out=d.incidents.find(i=>i.key===b.key);if(!out){out={id:Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join(''),message:String(b.message||'Richiesta demo').slice(0,500),state:'received',created:now,key:b.key};d.incidents.unshift(out)}
 }else if(action==='ack'||action==='close'){
 requireRole(['staff','organizer','admin']);const i=d.incidents.find(i=>i.id===b.id);if(!i)fail('Richiesta non disponibile');
 if(action==='ack'){if(i.state!=='received')fail('Richiesta già assegnata');i.state='acknowledged';i.assignee=demoRole}else{if(i.state!=='acknowledged'||String(b.reason||'').trim().length<5)fail('Prendere in carico e indicare il motivo');if(i.assignee!==demoRole&&!['organizer','admin'].includes(demoRole))fail('Chiusura riservata al responsabile');if(b.reason.length>500)fail('Motivazione troppo lunga');i.state='closed';i.reason=b.reason;i.closed_by=demoRole;i.closed_at=now}out=i;
 }else fail('Operazione non disponibile');
 localStorage.setItem(DEMO_STORE,JSON.stringify(d));return out;
}
const nativeFetch=window.fetch.bind(window);
window.fetch=async (input,init={})=>{
 const url=new URL(typeof input==='string'?input:input.url,location.href);
 if(url.origin!==location.origin||!url.pathname.startsWith('/api/'))return nativeFetch(input,init);
 try{if(!navigator.onLine)throw Error('Rete assente');const action=url.pathname.slice(5);const b=init.body?JSON.parse(init.body):{};const result=await demoLocked(()=>demoOperation(action,b));return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}})}catch(e){return new Response(JSON.stringify({error:e.message}),{status:400,headers:{'Content-Type':'application/json'}})}
};

