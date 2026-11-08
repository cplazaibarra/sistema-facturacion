import json, math
from pathlib import Path
from collections import defaultdict
p=Path('/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/docs/qa/auditoria_erp_20261020')
d=json.loads((p/'datos_lectura.json').read_text())
cfg={r['key']:json.loads(r['json']) if isinstance(r['json'],str) else r['json'] for r in d['config']}
catalog={r['code']:float(r.get('price') or 0) for r in cfg['inventory_items']}
entries=defaultdict(list)
for r in d['entries']: entries[r['product_id']].append(r)
costs=[]
for r in d['products']:
    if r['is_deleted']: continue
    pid=r['id']; e=entries[pid]; qty=sum(float(x['quantity']) for x in e)
    quote=sum(float(x['total']) for x in e)/qty if qty>0 else catalog.get(r['sku'],0)
    listing=d['price_list_costs'].get(str(pid),catalog.get(r['sku']))
    listing=float(listing or r['cost'] or 0)
    costs.append({'id':pid,'sku':r['sku'],'name':r['name'],'type':r['product_type'],'master_cost':r['cost'],'ppp':d['ppp'][str(pid)],'quote_base':round(quote,4),'list_base':round(listing,4)})
sales=[]; invalid=[]
for s in d['sales']:
    lines=json.loads(s['products_json'] or '[]')
    calc=sum(float(l.get('quantity') or 0)*float(l.get('price',l.get('unit_price',0)) or 0)*(1-float(l.get('discount') or 0)/100) for l in lines)
    stored_sub=sum(float(l.get('subtotal',float(l.get('quantity') or 0)*float(l.get('price',l.get('unit_price',0)) or 0)*(1-float(l.get('discount') or 0)/100))) for l in lines)
    total=float(s['total_amount'] or 0)
    sales.append({'id':s['id'],'folio':s['sale_number'],'status':s['status'],'line_count':len(lines),'lines_net':round(calc,2),'stored_subtotals':round(stored_sub,2),'saved_total':total,'print_total':round(stored_sub)+math.floor(round(stored_sub)*.19+.5),'saved_equals_lines':abs(calc-total)<.02,'saved_equals_gross':abs(round(calc)*1.19-total)<1,'line_details':lines})
    for l in lines:
        if float(l.get('quantity') or 0)<=0 or float(l.get('price',l.get('unit_price',0)) or 0)<0 or not 0<=float(l.get('discount') or 0)<=100: invalid.append({'folio':s['sale_number'],'line':l})
bad_items=[r for r in d['sale_items'] if abs(float(r['quantity'])*float(r['unit_cost_at_sale'])-float(r['total_cost_at_sale']))>.02]
bad_entries=[r for r in d['entries'] if abs(float(r['quantity'])*float(r['unit_price'])-float(r['total']))>.02]
bad_po=[r for r in d['purchase_order_items'] if abs(float(r['quantity_ordered'])*float(r['unit_price'])-float(r['total_price']))>.02]
approved=defaultdict(float)
for r in d['sale_payment_items']:
    if r['accounting_approved']: approved[r['sale_id']]+=float(r['payment_amount'])
overpaid=[{'folio':s['sale_number'],'total':s['total_amount'],'paid':approved[s['id']]} for s in d['sales'] if s['status'] not in ['Cancelada','Anulada','Cotización'] and approved[s['id']]>float(s['total_amount'])+.01]
production=[]
for ot in d['production_orders']:
    moves=[m for m in d['inventory_movements'] if m['reference_type']=='production_order' and m['reference_id']==ot['id']]
    inputs=sum(abs(float(m['quantity']))*float(m['unit_cost']) for m in moves if m['movement_type']=='PRODUCTION_INPUT')
    outputs=sum(float(m['quantity'])*float(m['unit_cost']) for m in moves if m['movement_type']=='PRODUCTION_OUTPUT')
    revised={r['movement_id']:float(r['new_unit_cost']) for r in d['inventory_cost_revaluations']}
    adjusted_input=sum(abs(float(m['quantity']))*revised.get(m['id'],float(m['unit_cost'])) for m in moves if m['movement_type']=='PRODUCTION_INPUT')
    adjusted_output=sum(float(m['quantity'])*revised.get(m['id'],float(m['unit_cost'])) for m in moves if m['movement_type']=='PRODUCTION_OUTPUT')
    production.append({'folio':ot['ot_number'],'status':ot['status'],'input_cost':inputs,'output_value':outputs,'delta':round(outputs-inputs,4),'effective_input_cost':adjusted_input,'effective_output_value':adjusted_output,'effective_delta':round(adjusted_output-adjusted_input,4),'header_unit_cost':ot['unit_cost']})
invoices=[]
for inv in d['purchase_invoices']:
    net=sum(float(e['total']) for e in d['entries'] if e['inventory_entry_id']==inv['inventory_entry_id'])
    invoices.append({'id':inv['id'],'linked_receipt':inv['inventory_entry_id'],'net':net if inv['inventory_entry_id'] else None,'invoice_amount':inv['invoice_amount'],'expected_gross':round(net*1.19,2) if inv['inventory_entry_id'] else None,'delta':round(float(inv['invoice_amount'])-net*1.19,2) if inv['inventory_entry_id'] else None})
result={'counts':d['counts'],'costs':costs,'cost_disagreements':[c for c in costs if abs(c['quote_base']-c['list_base'])>.01],'zero_quote_positive_ppp':[c for c in costs if c['quote_base']==0 and c['ppp']>0],'sales':sales,'invalid_sale_lines':invalid,'bad_sale_cost_arithmetic':bad_items,'bad_receipt_arithmetic':bad_entries,'bad_purchase_order_arithmetic':bad_po,'overpaid_approved':overpaid,'production':production,'purchase_invoices':invoices,'categories':cfg['price_list_config']}
debt_bad=[]
for i in d['debt_installments']:
    total=sum(float(i[k]) for k in ['capital','interest','fees','insurance','other_charges'])
    paid=sum(float(x['payment_amount']) for x in d['debt_payments'] if x['debt_installment_id']==i['id'])
    if abs(total-float(i['total_amount']))>.01 or abs(paid-float(i['paid_amount']))>.01 or abs(float(i['balance'])-(total-paid))>.01: debt_bad.append(i['id'])
result['debt_installment_inconsistencies']=debt_bad
(p/'resultados_numericos.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['counts','sales','costs']},ensure_ascii=False,indent=2))
print('COTIZACIONES',json.dumps([{k:v for k,v in s.items() if k!='line_details'} for s in sales if s['folio'].startswith('COT-')],ensure_ascii=False))
