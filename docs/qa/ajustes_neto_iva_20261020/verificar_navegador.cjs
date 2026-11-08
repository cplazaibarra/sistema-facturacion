const fs = require('fs');
const {execFileSync} = require('child_process');
const {chromium} = require('/home/cplaza/.cache/ms-playwright-go/1.57.0/package');
const root='/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion';
const out=root+'/docs/qa/auditoria_erp_20261020';
const token=execFileSync(root+'/venv/bin/python',['-c',`import os; from dotenv import load_dotenv; from flask import Flask; from flask.sessions import SecureCookieSessionInterface; load_dotenv(); app=Flask(__name__); app.secret_key=os.environ['SECRET_KEY']; print(SecureCookieSessionInterface().get_signing_serializer(app).dumps({'user_id':1,'username':'admin','role_name':'Administrativo','full_name':'Administrador','permissions':{k:True for k in ['dashboard','ventas','inventario','productos','administracion','usuarios','reportes','configuracion','crear_registros','aprobar_registros']}}))`],{cwd:root}).toString().trim();
function assert(v,m){if(!v)throw new Error(m);}
(async()=>{
 const browser=await chromium.launch({executablePath:'/home/cplaza/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',headless:true,args:['--no-sandbox']});
 try {
 const context=await browser.newContext({viewport:{width:1365,height:1000}});
 await context.addCookies([{name:'session',value:token,url:'http://127.0.0.1:5001'}]);
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 // Reject all write requests so this check cannot submit operational documents.
 await page.route('**/*',route=>['GET','HEAD','OPTIONS'].includes(route.request().method())?route.continue():route.abort());
 let response=await page.goto('http://127.0.0.1:5001/ventas/cotizaciones?filter=&page=1');
 assert(response.status()===200,'Cotizaciones no responde 200');
 await page.locator('a[onclick^="openCotizacionDetail"]').first().click();
 await page.emulateMedia({media:'print'});
 const detail=await page.evaluate(()=>{
  const text=id=>document.getElementById(id).textContent.trim();
  const logo=document.querySelector('#quotation-print-logo img');
  return {net:text('modal-cot-neto'),vat:text('modal-cot-iva'),total:text('modal-cot-total'),sidebar:getComputedStyle(document.querySelector('.sidebar')).display,logoLoaded:logo?.complete&&logo.naturalWidth>0};
 });
 assert(detail.sidebar==='none','La barra lateral aparece al imprimir');
 assert(detail.logoLoaded,'El logo no carga');
 const pesos=s=>Number(s.replace(/[^0-9-]/g,''));
 assert(pesos(detail.net)+pesos(detail.vat)===pesos(detail.total),'Desglose impreso no cuadra');
 await page.pdf({path:out+'/cotizacion_imprimible_validada.pdf',format:'A4',printBackground:true});
 await page.emulateMedia({media:'screen'});
 response=await page.goto('http://127.0.0.1:5001/ventas/cotizacion/nueva');
 assert(response.status()===200,'Formulario no responde 200');
 const select=page.locator('.product-select').first();
 if(await select.count()===0){await page.locator('button').filter({hasText:/Agregar Producto/i}).first().click();}
 const sel=page.locator('.product-select').first();
 await page.locator('.product-custom-select').first().click();
 await page.locator('.product-dropdown-menu input').first().fill('Ulmo');
 await page.locator('.dropdown-opt[data-product-id="60"]').first().click();
 await page.locator('input[name="quantity[]"]').first().fill('3');
 await page.locator('input[name="unit_price[]"]').first().fill('10000');
 await page.locator('input[name="discount[]"]').first().fill('10');
 await page.locator('input[name="discount[]"]').first().dispatchEvent('input');
 const form=await page.evaluate(()=>({net:document.getElementById('neto-val')?.textContent,vat:document.getElementById('iva-val')?.textContent,total:document.getElementById('total-val')?.textContent}));
 assert(form.net&&pesos(form.net)===27000,'Neto en formulario incorrecto: '+JSON.stringify(form));
 assert(pesos(form.vat)===5130&&pesos(form.total)===32130,'IVA/total del formulario incorrectos');
 await page.screenshot({path:out+'/formulario_neto_iva.png',fullPage:true});
 assert(errors.length===0,'Errores JavaScript: '+JSON.stringify(errors));
 fs.writeFileSync(out+'/navegador.json',JSON.stringify({detail,form,errors,writesBlocked:true},null,2));
 console.log(JSON.stringify({detail,form,errors,writesBlocked:true}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1);});
