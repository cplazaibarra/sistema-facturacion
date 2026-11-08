const fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('/home/cplaza/.cache/ms-playwright-go/1.57.0/package');
const out=process.env.CERTIFICATION_OUT,base=process.env.CERTIFICATION_BASE,python=process.env.CERTIFICATION_PYTHON||path.resolve(out,'../venv/bin/python');
if(base!=='http://127.0.0.1:15021')throw Error('Unsafe browser');
execFileSync(python,[path.join(out,'scripts/browser_critical_seed.py')],{cwd:process.env.CERTIFICATION_WORK,env:process.env});
const manifest=JSON.parse(fs.readFileSync(path.join(out,'evidencia/critical_manifest.json')));
const token=execFileSync(python,['-c',`import os;from flask import Flask;from flask.sessions import SecureCookieSessionInterface;a=Flask(__name__);a.secret_key=os.environ['SECRET_KEY'];print(SecureCookieSessionInterface().get_signing_serializer(a).dumps({'user_id':1,'username':'admin','role_name':'Administrativo','permissions':{k:True for k in ['compras','ventas','inventario','reportes','administracion','operario_bodega','crear_registros']}}))`],{env:process.env}).toString().trim();
const db=(q,p=[])=>JSON.parse(execFileSync(python,['-c',`import sys,json;from core.database import get_connection
with get_connection() as c,c.cursor() as r:r.execute(sys.argv[1],json.loads(sys.argv[2]));print(json.dumps([dict(x) for x in r.fetchall()],default=str))`,q,JSON.stringify(p)],{cwd:process.env.CERTIFICATION_WORK,env:process.env}).toString());
function assert(v,msg){if(!v)throw Error(msg)}
const results=[];const record=(r)=>{results.push(r);fs.writeFileSync(path.join(out,'evidencia/navegador_critico.json'),JSON.stringify(results,null,2));};
(async()=>{const browser=await chromium.launch({executablePath:'/home/cplaza/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',headless:true,args:['--no-sandbox']});
try{const ctx=await browser.newContext({viewport:{width:1440,height:1080}});await ctx.addCookies([{name:'session',value:token,url:base}]);const page=await ctx.newPage();page.setDefaultTimeout(8000);page.on('dialog',d=>d.accept());await page.route('**/*',r=>{const u=new URL(r.request().url());if(['127.0.0.1','localhost'].includes(u.hostname)&&u.origin!==base)return r.abort();return r.continue()});
for(const m of manifest){const v=m.v;
 for(const feature of ['cxp','flujo_caja','gastos','conciliacion','produccion']){const r={id:`UI-CRIT-${feature}-${v}`,functionality:feature,variant:v,initial_data:m,action:'Interacción en controles reales y contraste PostgreSQL',status:'NOT VERIFIED'};
 try{
 if(feature==='cxp'){
  await page.goto(base+'/compras/cuentas-por-pagar?search='+m.invoice_doc);await page.locator('tr').filter({hasText:m.invoice_doc}).getByRole('button',{name:'Registrar Pago'}).click();
  await page.locator('#modal-amount').fill(String(v===1?2000:v===2?5900:v===3?11901:v===4?11900:3000));await page.locator('#modal-date + input').fill('20/10/2026');await page.locator('#modal-date + input').press('Tab');
  // Select an existing account through the remote datalist.
  const input=page.locator('#modal-bank-account-search');await input.fill(m.account.account_number);await page.waitForFunction(account=>[...document.querySelectorAll('#modal-bank-account-options option')].some(e=>e.value.includes(account)),m.account.account_number);
  const label=await page.evaluate(account=>[...document.querySelectorAll('#modal-bank-account-options option')].find(e=>e.value.includes(account)).value,m.account.account_number);await input.fill(label);await input.dispatchEvent('change');
  if(v===3){assert(!await page.locator('#modal-amount').evaluate(e=>e.checkValidity()),'Frontend acepta sobrepago');
   const resp=await page.evaluate(async id=>{const f=document.getElementById('pay-form');return (await fetch(f.action,{method:'POST',body:new FormData(f)})).status},m.invoice_id);r.backend_status=resp;
  }else{await page.locator('#pay-form button[type=submit]').click();await page.waitForLoadState('domcontentloaded');}
  const row=db('SELECT payment_amount,payment_status FROM purchase_invoices WHERE id=%s',[m.invoice_id])[0];r.expected=v===3?0:v===1?2000:v===2?5900:v===4?11900:3000;r.actual=Number(row.payment_amount||0);assert(r.actual===r.expected,'Abono persistido difiere');
  await page.goto(base+'/compras/cuentas-por-pagar?search='+m.invoice_doc+'&filtro=todas');assert((await page.locator('body').innerText()).includes(m.invoice_doc),'Factura no visible');
 }else if(feature==='flujo_caja'){
  await page.goto(base+'/reporteria/flujo-caja?start_date=2026-10-01&end_date=2026-11-30&bank_account_id='+m.account.id+'&origin=cxp');
  const rows=db('SELECT invoice_amount,COALESCE(payment_amount,0) paid FROM purchase_invoices WHERE id=%s',[m.invoice_id]);r.expected={real:Number(rows[0].paid),pending:11900-Number(rows[0].paid)};
  const text=await page.locator('body').innerText();assert(text.includes(m.invoice_doc),'Compromiso/pago ausente del flujo');r.actual=text;const projected=await page.locator('.stat-card').nth(2).innerText();const shown=Number((projected.match(/-?\$([\d.,]+)/)||['',''])[1].replace(/[^0-9]/g,''));assert(shown===r.expected.pending,'Saldo proyectado visible difiere');
 }else if(feature==='gastos'){
  await page.goto(base+'/reporteria/cuentas-por-pagar?search=GOP-'+String(m.occurrence_id).padStart(5,'0'));
  const button=page.locator('button[onclick^="openGastoOccurrenceModal"]').first();await button.click();await page.locator('#gasto-mark-paid').check();await page.locator('#gasto-payment-amount').fill(String(v===3?11901:v===4?11900:2000));await page.locator('#gasto-paid-date + input').fill('20/10/2026');await page.locator('#gasto-paid-date + input').press('Tab');await page.locator('#gasto-bank-account').selectOption(String(m.account.id));
  if(v===3){assert(!await page.locator('#gasto-payment-amount').evaluate(e=>e.checkValidity()),'Gasto frontend acepta sobrepago');await page.evaluate(async()=>{const f=document.getElementById('gasto-occurrence-form');await fetch(f.action,{method:'POST',body:new FormData(f)})});}
  else{await page.locator('#gasto-occurrence-form button[type=submit]').click();await page.waitForLoadState('domcontentloaded');}
  const row=db('SELECT amount,payment_amount,status FROM operational_expense_occurrences WHERE id=%s',[m.occurrence_id])[0];r.expected=v===3?0:v===4?11900:2000;r.actual=Number(row.payment_amount||0);assert(r.actual===r.expected,'Gasto abono incorrecto');
 }else if(feature==='conciliacion'){
  await page.goto(base+'/reporteria/conciliacion-bancaria?bank_account_id='+m.account.id);
  const row=page.locator('tr').filter({has:page.locator(`button[onclick*="abrirModalConciliacion(${m.tx_id})"]`)});
  await page.locator(`button[onclick*="abrirModalConciliacion(${m.tx_id})"]`).click();
  if(v===2||v===3){await page.waitForFunction(()=>!document.getElementById('matchingCandidatesList').innerText.includes('Cargando'));
   const saleName=db('SELECT s.sale_number FROM sale_payment_items p JOIN sales s ON s.id=p.sale_id WHERE p.id=%s',[m.payment_id])[0].sale_number;
   assert(!(await page.locator('#matchingCandidatesList').innerText()).includes(saleName),'Se ofrece un cobro con monto distinto');
   assert(await page.locator('#btnEjecutarConciliacion').isDisabled(),'Diferencia permite conciliación UI');
   const rejected=await page.evaluate(async m=>{const res=await fetch(`/reporteria/conciliacion-bancaria/movimientos/${m.tx_id}/conciliar`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reconciled_type:'SALE_PAYMENT',reconciled_id:m.payment_id})});return res.status},m);
   assert(rejected===400,'Backend no rechaza el cobro específico distinto');r.backend_status=rejected;}
  else{await page.locator('#matchingCandidatesList > div').first().click();await Promise.all([page.waitForResponse(r=>r.url().endsWith('/conciliar')&&r.request().method()==='POST'),page.locator('#btnEjecutarConciliacion').click()]);await page.waitForLoadState('domcontentloaded');}
  const actual=db('SELECT reconciliation_status FROM bank_transactions WHERE id=%s',[m.tx_id])[0].reconciliation_status;r.actual=actual;r.expected=v===2||v===3?'PENDIENTE':'CONCILIADO';assert(actual===r.expected,'Conciliación persistida incorrecta');
 }else{
  await page.goto(base+`/operario/ot/${m.order_id}/finalizar`);await page.locator('[name=actual_quantity]').fill(String(v===2?1:2));await page.locator('[name=output_lot_number]').fill('CERT-UI-OUT-'+m.order_id);await page.getByRole('button',{name:'CONFIRMAR Y TERMINAR'}).click();await page.waitForLoadState('domcontentloaded');
  const rows=db("SELECT quantity,unit_cost FROM inventory_movements WHERE reference_type='production_order' AND reference_id=%s AND movement_type='PRODUCTION_OUTPUT'",[m.order_id]);r.expected=v===3||v===4?0:v===2?1:2;r.actual=rows.reduce((n,x)=>n+Number(x.quantity),0);assert(r.actual===r.expected,'Producción no respeta consumo');if(rows.length)assert(Number(rows[0].unit_cost)===1000,'Costo producción incorrecto');
 }
 r.status='PASS';await page.screenshot({path:path.join(out,`evidencia/${r.id}.png`),fullPage:true});
 }catch(e){r.status='FAIL';r.error=e.message;await page.screenshot({path:path.join(out,`evidencia/${r.id}-error.png`),fullPage:true}).catch(()=>{});}record(r);
 }
}
console.log(JSON.stringify(results.reduce((a,r)=>(a[r.status]=(a[r.status]||0)+1,a),{})));
}finally{await browser.close()}})().catch(e=>{console.error(e.stack);process.exit(1)});
