const fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('/home/cplaza/.cache/ms-playwright-go/1.57.0/package');
const out=process.env.CERTIFICATION_OUT,base=process.env.CERTIFICATION_BASE,python=path.resolve(out,'../venv/bin/python');
if(base!=='http://127.0.0.1:15021')throw Error('Unsafe origin');
execFileSync(python,[path.join(out,'scripts/browser_extended_seed.py')],{cwd:process.env.CERTIFICATION_WORK,env:process.env,stdio:['ignore',fs.openSync(path.join(out,'evidencia/browser_extended_seed.log'),'w'),fs.openSync(path.join(out,'evidencia/browser_extended_seed_errors.log'),'w')]});
const manifest=JSON.parse(fs.readFileSync(path.join(out,'evidencia/browser_extended_manifest.json')));
const sign=role=>execFileSync(python,['-c',`import os,sys;from flask import Flask;from flask.sessions import SecureCookieSessionInterface;a=Flask(__name__);a.secret_key=os.environ['SECRET_KEY'];print(SecureCookieSessionInterface().get_signing_serializer(a).dumps({'user_id':1,'username':'admin','role_name':sys.argv[1],'permissions':{}}))`,role],{env:process.env}).toString().trim();
const previous=process.env.CERT_EXT_RETRY==='1'?JSON.parse(fs.readFileSync(path.join(out,'evidencia/navegador_ampliado.json'))):[];
const retry=new Set(previous.filter(r=>r.status==='BLOCKED').map(r=>r.id));
const results=previous.filter(r=>!retry.has(r.id));function assert(v,m){if(!v)throw Error(m)}
const money=s=>{const raw=String(s).replace(/[^0-9.,-]/g,'');const parts=raw.split(/[.,]/);return Number(parts.length>1&&parts.at(-1).length<=2?parts.slice(0,-1).join('')+'.'+parts.at(-1):parts.join(''));};
(async()=>{const browser=await chromium.launch({executablePath:'/home/cplaza/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',headless:true,args:['--no-sandbox']});
try{const ctx=await browser.newContext({viewport:{width:1440,height:1080}});await ctx.route('**/*',route=>{const u=new URL(route.request().url());return ['127.0.0.1','localhost'].includes(u.hostname)&&u.origin!==base?route.abort():route.continue();});await ctx.addCookies([{name:'session',value:sign('Administrativo'),url:base}]);const page=await ctx.newPage();page.setDefaultTimeout(4000);
for(const m of manifest){
 const specs=[
 ['clientes','/ventas/clientes?search='+encodeURIComponent(m.customer),m.customer],
 ['ppp_fifo','/productos/'+m.raw_id+'/kardex',m.product.sku],
 ['despacho','/ventas?filter=&search='+m.sale,m.sale],
 ['recetas','/produccion/recetas?search='+m.recipe,m.recipe],
 ['deudas','/reporteria/deudas/'+m.debt_id,m.debt_name],
 ['conciliacion','/reporteria/conciliacion-bancaria?bank_account_id='+m.account,m.transaction.description],
 ['seguridad','/usuarios',null],
 ['ajustes','/inventario/ajustes/'+m.adjustment_id,m.product.sku],
 ['embalajes','/ventas?filter=&search='+m.sale,m.sale],
 ['precios','/administracion/listas-precios?search='+m.sold_sku,m.sold_sku],
 ['trazabilidad','/trazabilidad?lot_id='+m.lot_id,m.lot],
 ['operario','/operario/ot/'+m.order_id+'/finalizar',m.order],
 ['agenda','/produccion/calendario?date=2026-10-'+(21+m.v),m.order],
 ['excel_productos','/productos?search='+m.product.sku,m.product.sku],
 ['excel_bancos','/reporteria/conciliacion-bancaria?bank_account_id='+m.account,m.transaction.description],
 ['excel_deudas','/reporteria/deudas/'+m.debt_id,m.debt_name],
 ['usuarios_roles','/roles','Administrativo'],
 ['informacion_empresa','/administracion/informacion',null]
 ];
 for(const [feature,route,target]of specs){if(process.env.CERT_EXT_RETRY==='1'&&!retry.has(`UI-${feature}-${m.v}`))continue;const r={id:`UI-${feature}-${m.v}`,functionality:feature,variant:m.v,initial_data:m,expected:target,action:'Comprobación de interfaz real y dato persistido; exportaciones mediante control de descarga',status:'NOT VERIFIED'};
 try{
  const response=await page.goto(base+route,{waitUntil:'domcontentloaded',timeout:20000});r.http=response.status();assert(response.status()===200,'HTTP '+response.status());
  if(feature==='seguridad'){
   const denied=await browser.newContext();await denied.addCookies([{name:'session',value:sign('CERT Sin Permisos'),url:base}]);const p=await denied.newPage();const q=await p.goto(base+['/usuarios','/roles','/administracion/informacion','/administracion/cuentas-bancarias','/inventario/ajustes'][m.v-1]);r.actual={http:q.status(),body:(await p.locator('body').innerText()).slice(0,800)};assert(q.status()===403&&/denegad|permiso/i.test(r.actual.body),'Permisos de interfaz no restringen acceso');await denied.close();
  }else if(feature==='informacion_empresa'){
   const encoded=execFileSync(python,['-c',`import io,sys,base64;from PIL import Image;b=io.BytesIO();Image.new('RGB',(20+int(sys.argv[1]),20+int(sys.argv[1])),'green').save(b,format='PNG');print(base64.b64encode(b.getvalue()).decode())`,String(m.v)]).toString().trim();
   await page.locator('[name=company_logo]').setInputFiles({name:'cert.png',mimeType:'image/png',buffer:Buffer.from(encoded,'base64')});await page.getByRole('button',{name:'Guardar logo'}).click();await page.waitForLoadState('domcontentloaded');
   r.actual=await page.locator('.settings-card img').evaluate(e=>({loaded:e.complete&&e.naturalWidth>0,width:e.naturalWidth}));assert(r.actual.loaded&&r.actual.width===20+m.v,'Logo no persistido con sus dimensiones');
  }else if(feature==='despacho'||feature==='embalajes'){
   const row=page.locator('tr').filter({hasText:m.sale}).first();const text=await row.innerText();assert(text.includes('En Preparación'),'Estado operativo visible incorrecto');
   await row.locator('a[onclick^="openVentaDetailModal"]').click();
   await page.waitForFunction(()=>document.getElementById('modal-fin-pkg-cost').textContent!=='$0');
   r.actual=await page.evaluate(()=>Object.fromEntries(['neto','prod-cost','pkg-cost','total-cost','margin-val'].map(k=>[k,document.getElementById('modal-fin-'+k).textContent])));
   assert(money(r.actual['prod-cost'])===2000*m.v&&money(r.actual['pkg-cost'])===100*m.v&&money(r.actual['margin-val'])===900*m.v,'Costos/margen de despacho no coinciden');
  }else if(feature.startsWith('excel_')){
   const control=page.getByRole('link',{name:/exportar.*excel|excel.*exportar|exportar movimientos/i}).or(page.getByRole('button',{name:/exportar.*excel|excel.*exportar/i})).first();
   if(feature==='excel_productos')await page.getByText('Exportar Excel',{exact:true}).click();
   const pending=page.waitForEvent('download',{timeout:6000}).catch(()=>null);if(feature==='excel_productos')await page.getByRole('link',{name:/Exportar Filtro Actual/}).click();else await control.click();const download=await pending;assert(download,'Timeout de descarga Excel');const file=path.join(out,`evidencia/${feature}-${m.v}.xlsx`);await download.saveAs(file);
   const proof=JSON.parse(execFileSync(python,['-c',`import sys,json;from openpyxl import load_workbook;w=load_workbook(sys.argv[1],data_only=True);a=[str(c) for r in w.active.iter_rows(values_only=True) for c in r if c is not None];print(json.dumps({'rows':w.active.max_row,'values':a}))`,file],{env:process.env}).toString());r.actual={rows:proof.rows};assert(proof.rows>1,'Excel vacío');
   if(feature==='excel_productos')assert(proof.values.includes(m.product.sku),'SKU ausente del Excel');
   if(feature==='excel_bancos')assert(proof.values.some(x=>Number(x)===11900+m.v),'Monto bancario ausente del Excel');
   if(feature==='excel_deudas')assert(proof.values.filter(x=>Number(x)>0).length>=3,'Cuotas ausentes del Excel');
  }else{
   const body=await page.locator('body').innerText();assert(body.includes(String(target)),'Dato propio no localizado en pantalla');r.actual=String(target);
   if(['ppp_fifo','precios'].includes(feature)){const numbers=[...body.matchAll(/\$\s*([\d.,]+)/g)].map(x=>money(x[1]));r.actual={target,currency_values:numbers};assert(numbers.includes(feature==='precios'?m.price_cost:m.cost),'Costo PPP no coincide en pantalla');}
   if(feature==='conciliacion'){const row=page.locator('tr').filter({hasText:target}).first();const text=await row.innerText();assert(text.replace(/[.,]/g,'').includes(String(11900+m.v)),'Monto conciliable visible incorrecto');r.actual=text;}
  }
  if(r.status==='NOT VERIFIED')r.status='PASS';if(m.v===1)await page.screenshot({path:path.join(out,`evidencia/UI-extra-${feature}.png`),fullPage:true});
 }catch(e){r.status=/Timeout|no localizado|pantalla|HTTP 404/.test(e.message)?'BLOCKED':'FAIL';r.error=e.message;}
 results.push(r);fs.writeFileSync(path.join(out,'evidencia/navegador_ampliado.json'),JSON.stringify(results,null,2));
 }
}
console.log(JSON.stringify(results.reduce((a,r)=>(a[r.status]=(a[r.status]||0)+1,a),{})));
}finally{await browser.close();}})().catch(e=>{console.error(e.stack);process.exit(1)});
