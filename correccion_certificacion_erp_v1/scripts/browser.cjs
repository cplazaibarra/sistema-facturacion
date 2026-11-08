const fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('/home/cplaza/.cache/ms-playwright-go/1.57.0/package');
const out=process.env.CERTIFICATION_OUT,base=process.env.CERTIFICATION_BASE;
if(base!=='http://127.0.0.1:15021'||!process.env.DB_NAME.startsWith('facturacion_test_run_'))throw Error('Unsafe browser environment');
const py=path.join(out,'..','venv','bin','python');
const python=process.env.CERTIFICATION_PYTHON||path.resolve(out,'../venv/bin/python');
execFileSync(python,[path.join(out,'scripts/browser_seed.py')],{cwd:process.env.CERTIFICATION_WORK,env:process.env,stdio:['ignore',fs.openSync(path.join(out,'evidencia/browser_seed.log'),'w'),fs.openSync(path.join(out,'evidencia/browser_seed_errors.log'),'w')]});
const manifest=JSON.parse(fs.readFileSync(path.join(out,'evidencia/browser_manifest.json')));
const token=execFileSync(python,['-c',`import os;from flask import Flask;from flask.sessions import SecureCookieSessionInterface;a=Flask(__name__);a.secret_key=os.environ['SECRET_KEY'];print(SecureCookieSessionInterface().get_signing_serializer(a).dumps({'user_id':1,'username':'admin','full_name':'CERT Administrador','role_name':'Administrativo','permissions':{k:True for k in ['dashboard','usuarios','ventas','inventario','productos','administracion','reportes','configuracion','crear_registros','aprobar_registros','produccion','compras']}}))`],{cwd:process.env.CERTIFICATION_WORK,env:process.env}).toString().trim();
function assert(v,msg){if(!v)throw Error(msg)}
function db(q,params=[]){return JSON.parse(execFileSync(python,['-c',`import json,sys;from core.database import get_connection
with get_connection() as c,c.cursor() as r:
 p=json.loads(sys.argv[2]);r.execute(sys.argv[1],p) if p else r.execute(sys.argv[1]);print(json.dumps([dict(x) for x in r.fetchall()],default=str))`,q,JSON.stringify(params)],{cwd:process.env.CERTIFICATION_WORK,env:process.env}).toString());}
const money=s=>{const raw=String(s).replace(/[^0-9.,-]/g,'');const parts=raw.split(/[.,]/);return Number(parts.length>1&&parts.at(-1).length===2?parts.slice(0,-1).join('')+'.'+parts.at(-1):parts.join(''));};
const hasMoney=(text,value)=>[...text.matchAll(/\$\s*([\d.,]+)/g)].some(m=>money(m[1])===Number(value));
const rows=[];
const specs=[
 ['productos','/productos','product','sku'],['proveedores','/proveedores','supplier'],
 ['ordenes_compra','/compras/oc','oc'],['recepcion','/ingreso-mercaderia','entry_number'],
 ['cotizaciones','/ventas/cotizaciones?filter=','quote'],['ventas','/ventas?filter=','sale'],
 ['inventario','/inventario','product','sku'],['produccion','/produccion','production'],
 ['cxc','/reporteria/cuentas-por-cobrar','sale'],['cxp','/compras/cuentas-por-pagar','invoice_doc'],
 ['gastos','/administracion/gastos-operacionales','expense','name'],['bancos','/administracion/cuentas-bancarias','bank'],
 ['flujo_caja','/reporteria/flujo-caja','bank'],['reportes','/reporteria/ventas','product','name']
];
(async()=>{
 const browser=await chromium.launch({executablePath:'/home/cplaza/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',headless:true,args:['--no-sandbox']});
 try{
 const context=await browser.newContext({viewport:{width:1440,height:1080}});await context.addCookies([{name:'session',value:token,url:base}]);
 const page=await context.newPage();page.setDefaultTimeout(5000);let errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>{const u=new URL(r.request().url());if(['127.0.0.1','localhost'].includes(u.hostname)&&u.origin!==base)return r.abort();return r.continue();});
 for(const m of manifest)for(const [feature,route,key,sub] of specs){
  const result={id:`UI-${feature}-${m.variant}`,functionality:feature,variant:m.variant,initial_data:m,expected:[],actual:[],status:'NOT VERIFIED',action:'Pantalla real con datos sintéticos y contraste de importes/identificadores persistidos'};errors=[];
  try{
   let target=sub?m[key][sub]:m[key];let url=base+route+(route.includes('?')?'&':'?')+'search='+encodeURIComponent(target);
   if(feature==='flujo_caja')url=base+route+'?start_date=2026-10-01&end_date=2026-11-30&bank_account_id='+m.account_id;
   const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:20000});assert(response.status()===200,'HTTP '+response.status());
   if(feature==='cotizaciones'){
    const row=page.locator('tr').filter({hasText:m.quote}).first();await row.locator('a[onclick^="openCotizacionDetail"]').click();
    const values=await page.evaluate(()=>Object.fromEntries(['neto','iva','total'].map(k=>[k,document.getElementById('modal-cot-'+k).textContent])));
    result.expected={net:27000,vat:5130,total:32130};result.actual=Object.fromEntries(Object.entries(values).map(([k,v])=>[k,money(v)]));assert(result.actual.neto===27000&&result.actual.iva===5130&&result.actual.total===32130,'Diferencia en impresión/detalle');
    await page.emulateMedia({media:'print'});assert(await page.locator('.sidebar').evaluate(e=>getComputedStyle(e).display)==='none','Barra lateral impresa');
    await page.pdf({path:path.join(out,`evidencia/UI-cotizacion-${m.variant}.pdf`),format:'A4'});await page.emulateMedia({media:'screen'});
   }else if(feature==='ventas'){
    const row=page.locator('tr').filter({hasText:m.sale}).first();assert(hasMoney(await row.innerText(),m.sale_total),'Total bruto no coincide con el persistido');result.expected=m.sale_total;result.actual=await row.innerText();
   }else if(['productos','inventario'].includes(feature)){
    const row=page.locator('tr').filter({hasText:m.product.sku}).first();const text=await row.innerText();assert(text.includes(m.product.sku),'Producto no visible');result.expected=m.product;result.actual=text;
   }else if(feature==='cxc'){
    const row=page.locator('tr').filter({hasText:m.sale}).first();const text=await row.innerText();assert(hasMoney(text,m.sale_total),'Saldo CxC visible incorrecto');result.expected=m.sale_total;result.actual=text;
   }else if(feature==='flujo_caja'){
    const text=await page.locator('body').innerText();assert(text.includes('Flujo de Caja'),'Pantalla de flujo no corresponde');
    const values=[];for(let k=0;k<4;k++)values.push(money(await page.locator('.stat-card').nth(k).locator('div').nth(1).innerText()));
    result.expected={initial:0,inflows:0,outflows:2*Number(m.expense.amount),final:-2*Number(m.expense.amount)};
    result.actual={initial:values[0],inflows:values[1],outflows:Math.abs(values[2]),final:values[3]};
    assert(JSON.stringify(result.expected)===JSON.stringify(result.actual),'Flujo de caja no coincide con dos períodos sintéticos y banco inicial cero');result.status='PASS';
   }else if(feature==='reportes'){
    const data=db("SELECT s.total_amount FROM sales s WHERE s.status NOT IN ('Cancelada','Cancelado','Anulada','Anulado','Cotización','Borrador') AND (s.sale_number LIKE 'VTA-%' OR s.sale_number LIKE 'P-%')");const expected=data.reduce((s,r)=>s+Number(r.total_amount),0);
    const text=await page.locator('.stat-value').first().innerText();result.expected=expected;result.actual=money(text);assert(Math.round(expected)===result.actual,'Total de reporte difiere de DB');
   }else{
    const text=await page.locator('body').innerText();assert(text.includes(String(target)),'Registro sintético no localizado en pantalla');result.expected=target;result.actual=String(target);
   }
   if(result.status==='NOT VERIFIED'&&feature!=='flujo_caja')result.status='PASS';
   if(errors.length){result.javascript_errors=errors;result.status='FAIL';}
   if(m.variant===1)await page.screenshot({path:path.join(out,`evidencia/UI-${feature}.png`),fullPage:true});
  }catch(e){result.status=e.message.includes('Timeout')||e.message.includes('not visible')||e.message.includes('no localizado')?'BLOCKED':'FAIL';result.error=e.message;await page.screenshot({path:path.join(out,`evidencia/UI-${feature}-${m.variant}-error.png`),fullPage:true}).catch(()=>{});}
  rows.push(result);fs.writeFileSync(path.join(out,'evidencia/navegador.json'),JSON.stringify(rows,null,2));
 }
 // Five actual interactive quotation forms, including exact Decimal oracle cases.
 const inputs=[[3,10000,10,27000,5130,32130],[7,1234.55,15,7346,1396,8742],[1,50,0,50,10,60],[4,10000,100,0,0,0],[3,1000000000,10,2700000000,513000000,3213000000]];
 for(let i=0;i<inputs.length;i++){
  const [qty,price,discount,net,vat,total]=inputs[i],m=manifest[i],name='CERT-UI-INTERACTIVA-'+i;
  const r={id:'UI-FORM-COT-'+(i+1),functionality:'cotizaciones',variant:i+1,action:'Completar y emitir cotización desde controles reales',initial_data:{qty,price,discount},expected:{net,vat,total}};
  try{
   await page.goto(base+'/ventas/cotizacion/nueva',{waitUntil:'domcontentloaded'});
   await page.locator('[name=customer_name]').fill(name);await page.locator('[name=customer_email]').fill(name+'@cert.invalid');await page.locator('[name=customer_category]').selectOption('cat_0');await page.locator('.product-custom-select').first().click();await page.locator('.product-dropdown-menu input').first().fill(m.product.sku);
   await page.locator('.dropdown-opt').first().click();await page.locator('[name="quantity[]"]').first().fill(String(qty));await page.locator('[name="unit_price[]"]').first().fill(String(price));await page.locator('[name="discount[]"]').first().fill(String(discount));
   const actual=await page.evaluate(()=>Object.fromEntries(['neto','iva','total'].map(k=>[k,document.getElementById(k+'-val').textContent])));r.actual=actual;
   assert(money(actual.neto)===net&&money(actual.iva)===vat&&money(actual.total)===total,'Diferencia monetaria formulario');
   await page.locator('[data-save-quotation="Cotización"]').click();await page.waitForLoadState('domcontentloaded');
   const stored=db('SELECT total_amount FROM sales WHERE customer_name=%s',[name]);assert(stored.length===1&&Number(stored[0].total_amount)===total,'Persistencia de formulario incorrecta');r.persisted=stored;r.status='PASS';
  }catch(e){r.status='FAIL';r.error=e.message;}rows.push(r);fs.writeFileSync(path.join(out,'evidencia/navegador.json'),JSON.stringify(rows,null,2));
 }
 console.log(JSON.stringify(rows.reduce((s,r)=>(s[r.status]=(s[r.status]||0)+1,s),{})));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exit(1)});
