import json,os
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from core.test_database_guard import assert_current_test_database_authorized
assert_current_test_database_authorized()
from core.database import get_connection
out=Path(os.environ['CERTIFICATION_OUT'])
data={}
checks=[]
with get_connection() as c,c.cursor() as cur:
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    for row in cur.fetchall():
        name=row['tablename'];cur.execute('SELECT count(*) n FROM "'+name+'"');data[name]=cur.fetchone()['n']
    cur.execute("SELECT id,sale_number,total_amount,products_json FROM sales WHERE customer_name LIKE 'CERT-%' AND status<>'Cancelada' ORDER BY id")
    from reference import invoice
    for r in cur.fetchall():
        lines=json.loads(r['products_json'] or '[]')
        expected=invoice([(l['quantity'],l.get('price',l.get('unit_price',0)),l.get('discount',0)) for l in lines])['total']
        actual=Decimal(str(r['total_amount']))
        checks.append({'operation':r['sale_number'],'concept':'total neto + IVA','expected':str(expected),'actual':str(actual),'difference':str(actual-expected),'result':'PASS' if actual==expected else 'FAIL'})
    cur.execute("""SELECT p.id,p.sku,COALESCE(m.qty,0) AS ledger,COALESCE(l.qty,0) AS lots
        FROM products p LEFT JOIN(SELECT product_id,SUM(quantity) qty FROM inventory_movements GROUP BY product_id)m ON m.product_id=p.id
        LEFT JOIN(SELECT product_id,SUM(available_qty)qty FROM lot_stock GROUP BY product_id)l ON l.product_id=p.id
        WHERE p.sku LIKE 'CERT-%' AND p.requires_lot""")
    inventory=[dict(r) for r in cur.fetchall()]
    cur.execute("SELECT id,invoice_amount,payment_amount,payment_status FROM purchase_invoices WHERE COALESCE(payment_amount,0)>invoice_amount ORDER BY id")
    overpayments=[dict(r) for r in cur.fetchall()]
    cur.execute("""SELECT bt.id,bt.amount,spi.payment_amount,bt.reconciled_type
        FROM bank_transactions bt JOIN sale_payment_items spi ON bt.reconciled_type='SALE_PAYMENT' AND bt.reconciled_id=spi.id
        WHERE bt.reconciliation_status='CONCILIADO' AND bt.description LIKE 'CERT-%' AND abs(bt.amount-spi.payment_amount)>0""")
    mismatches=[dict(r) for r in cur.fetchall()]
(out/'evidencia/conteos_finales_sinteticos.json').write_text(json.dumps(data,indent=2))
(out/'evidencia/control_monetario_final.json').write_text(json.dumps({'document_checks':checks,'inventory_ledger_lots':inventory,'purchase_overpayments':overpayments,'reconciliation_amount_mismatches':mismatches},default=str,ensure_ascii=False,indent=2))
print(json.dumps(data))
