#!/usr/bin/env python3
"""Repair the audited OT-09270 valuation; dry-run by default, immutable ledger."""
import argparse
import json
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from core.database import get_connection
from repositories.inventory_revaluation_repo import revalue_inventory_movement


def plan_repair(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM production_orders WHERE ot_number='OT-09270' FOR UPDATE")
        order = cur.fetchone()
        if not order or order['status'] != 'Finalizada':
            raise ValueError('La OT auditada no existe o no está finalizada.')
        cur.execute("SELECT * FROM inventory_movements WHERE reference_type='production_order' AND reference_id=%s ORDER BY id FOR UPDATE", (order['id'],))
        originals = [dict(r) for r in cur.fetchall()]
        inputs = [r for r in originals if r['movement_type']=='PRODUCTION_INPUT']
        outputs = [r for r in originals if r['movement_type']=='PRODUCTION_OUTPUT']
        if len(inputs)!=2 or len(outputs)!=1 or float(outputs[0]['quantity'])!=3 or float(order['quantity'])!=3:
            raise ValueError('Los datos difieren de la OT auditada. Se requiere una revisión nueva.')
        output = outputs[0]
        cur.execute('SELECT count(*) AS n FROM sale_items WHERE product_id=%s', (output['product_id'],))
        if cur.fetchone()['n']:
            raise ValueError('Hay ventas con costo congelado de este producto; revisar su efecto antes de reparar.')
        pids=sorted({r['product_id'] for r in originals})
        cur.execute('SELECT id, cost FROM products WHERE id=ANY(%s) ORDER BY id FOR UPDATE',(pids,))
        states={r['id']:[Decimal(0),Decimal(0),Decimal(str(r['cost'] or 0))] for r in cur.fetchall()}
        cur.execute('''SELECT im.*, COALESCE(r.new_unit_cost,im.unit_cost) AS effective_cost
            FROM inventory_movements im LEFT JOIN (
                SELECT DISTINCT ON (movement_id) movement_id,new_unit_cost
                FROM inventory_cost_revaluations ORDER BY movement_id,id DESC
            ) r ON r.movement_id=im.id
            WHERE im.product_id=ANY(%s) ORDER BY im.created_at::timestamptz,im.id''',(pids,))
        input_ids={m['id'] for m in inputs}
        input_cost=Decimal(0)
        costs_by_product=defaultdict(lambda: [Decimal(0),Decimal(0)])
        current_output_cost=None
        for m in cur.fetchall():
            qty=Decimal(str(m['quantity'])); state=states[m['product_id']]
            if m['id'] in input_ids:
                if state[0] < abs(qty) or state[2]<=0:
                    raise ValueError('El historial de insumos no permite derivar un costo positivo con stock suficiente.')
                input_cost+=abs(qty)*state[2]
                costs_by_product[m['product_id']][0]+=abs(qty)
                costs_by_product[m['product_id']][1]+=abs(qty)*state[2]
            if m['id']==output['id']:
                current_output_cost=Decimal(str(m['effective_cost']))
            if qty>0:
                state[0]+=qty; state[1]+=qty*Decimal(str(m['effective_cost']))
                state[2]=state[1]/state[0]
            elif qty<0:
                state[1]=max(Decimal(0),state[1]-abs(qty)*state[2])
                state[0]=max(Decimal(0),state[0]-abs(qty))
        unit_cost=(input_cost/Decimal(str(output['quantity']))).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)
        cur.execute('SELECT * FROM production_order_items WHERE production_order_id=%s ORDER BY id FOR UPDATE',(order['id'],))
        order_items=[dict(r) for r in cur.fetchall()]
        return {'order_before':dict(order),'order_items_before':order_items,'movements_before':originals,
                'input_cost':input_cost,'output_movement_id':output['id'],'previous_effective_output_cost':current_output_cost,
                'new_unit_cost':unit_cost,'input_unit_costs':{pid:(v[1]/v[0]).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP) for pid,v in costs_by_product.items()}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--evidence',required=True)
    args=parser.parse_args()
    evidence=Path(args.evidence)
    if evidence.exists():
        raise ValueError('La evidencia ya existe; usa un archivo nuevo para conservar el respaldo.')
    evidence.parent.mkdir(parents=True,exist_ok=True)
    with get_connection() as conn:
        conn.set_session(isolation_level='SERIALIZABLE')
        plan=plan_repair(conn)
        evidence.write_text(json.dumps(plan,default=str,ensure_ascii=False,indent=2))
        if args.apply:
            if abs(plan['new_unit_cost']-plan['previous_effective_output_cost'])>Decimal('.000001'):
                result=revalue_inventory_movement(plan['output_movement_id'],plan['new_unit_cost'],
                    'Auditoría 2026-10-20: costo histórico de producción derivado del PPP anterior a cada consumo. Se conserva el movimiento original.',
                    reference_doc='OT-09270',created_by='Corrección autorizada por usuario',conn=conn)
                plan['revaluation']=result
            with conn.cursor() as cur:
                cur.execute('UPDATE production_orders SET unit_cost=%s WHERE id=%s',(plan['new_unit_cost'],plan['order_before']['id']))
                for pid,cost in plan['input_unit_costs'].items():
                    cur.execute('UPDATE production_order_items SET unit_cost=%s WHERE production_order_id=%s AND input_product_id=%s AND unit_cost IS NULL',(cost,plan['order_before']['id'],pid))
            conn.commit()
        else:
            conn.rollback()
    plan['applied']=args.apply
    evidence.write_text(json.dumps(plan,default=str,ensure_ascii=False,indent=2))
    print(json.dumps({'applied':args.apply,'order':'OT-09270','input_cost':str(plan['input_cost']),'new_unit_cost':str(plan['new_unit_cost']),'evidence':str(evidence)}))


if __name__=='__main__':
    main()
