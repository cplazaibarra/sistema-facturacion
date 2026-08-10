from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from db import (
    list_roles,
    get_sale_payments_map,
    delete_sale_payment_item,
    get_sale,
    get_sale_payment,
    list_sales_page_light,
    get_sale_payments_for_sales,
    get_sale_payment_items_totals,
    list_sale_payment_items,
    insert_sale_payment_item,
    upsert_sale_payment
)

pagos_bp = Blueprint('pagos', __name__)

def handle_payment_upload(field_name: str, prefix: str, sale_id: int) -> str | None:
    """Maneja la subida de archivos de pagos. Retorna la ruta del archivo o None"""
    file = request.files.get(field_name)
    if file and file.filename:
        safe_name = secure_filename(file.filename)
        ext = os.path.splitext(safe_name)[1]
        filename = secure_filename(f"{prefix}_{sale_id}_{int(datetime.utcnow().timestamp())}{ext}")
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return f"/uploads/{filename}"
    return None

@pagos_bp.route('/pagos', methods=['GET', 'POST'])
def pagos():
    """Módulo de pagos con workflow de validación"""
    roles = list_roles()
    current_role = (request.args.get('role') or '').strip()
    selected_sale_id = request.args.get('sale_id', type=int)
    payment_filter = (request.args.get('payment_status') or '').strip()
    per_page = 20
    if not current_role and roles:
        current_role = roles[0]["name"]
    elif not current_role:
        current_role = "Administrativo"

    form_errors: dict[int, str] = {}
    saved_sale_id = request.args.get('saved', type=int)

    if request.method == 'POST':
        sale_id = request.form.get('sale_id', type=int) or request.args.get('sale_id', type=int)
        actor_role = (request.form.get('actor_role') or '').strip() or current_role
        current_role = actor_role

        if not sale_id:
            form_errors[0] = "No se pudo identificar la venta. Recarga la página e intenta de nuevo."
        elif sale_id:
            payment_map = get_sale_payments_map()
            existing = payment_map.get(sale_id, {})

            # Eliminar pago individual si se solicitó
            delete_item_id = request.form.get('delete_payment_item_id', type=int)
            if delete_item_id:
                delete_sale_payment_item(delete_item_id)
                return redirect(url_for('pagos.pagos', role=actor_role, sale_id=sale_id, saved=sale_id))

            now = datetime.utcnow().isoformat(timespec='seconds')

            invoice_number = (request.form.get('invoice_number') or '').strip()
            invoice_file = handle_payment_upload('invoice_file', 'invoice', sale_id) or existing.get("invoice_file")
            invoice_due_date = (request.form.get('invoice_due_date') or '').strip()
            invoice_amount_raw = (request.form.get('invoice_amount') or '').strip()
            try:
                invoice_amount = float(invoice_amount_raw.replace(',', '.')) if invoice_amount_raw else None
            except ValueError:
                invoice_amount = None
            accounting_checked = request.form.get('accounting_approved') == 'on'
            accounting_comment = (request.form.get('accounting_comment') or '').strip()

            # Nuevo pago (múltiples pagos hasta completar factura)
            payment_item_amount_raw = (request.form.get('payment_item_amount_new') or '').strip()
            payment_item_date = (request.form.get('payment_item_date_new') or '').strip()
            try:
                payment_item_amount = float(payment_item_amount_raw.replace(',', '.')) if payment_item_amount_raw else 0
            except ValueError:
                payment_item_amount = 0

            payment_added = False
            if payment_item_amount > 0 and payment_item_date:
                payment_proof_file = handle_payment_upload('payment_proof_file_new', 'proof', sale_id)
                new_item = {
                    "sale_id": sale_id,
                    "payment_amount": payment_item_amount,
                    "payment_date": payment_item_date,
                    "payment_proof_file": payment_proof_file,
                    "created_at": now,
                }
                insert_sale_payment_item(new_item)
                payment_added = True

            payment_items = list_sale_payment_items(sale_id)
            totals_map = get_sale_payment_items_totals([sale_id])
            total_paid = float(totals_map.get(sale_id, 0))
            has_payment_items = len(payment_items) > 0

            if payment_item_amount_raw and payment_item_amount <= 0:
                form_errors[sale_id] = "El monto del pago debe ser mayor que 0."
            elif payment_item_amount_raw and not payment_item_date:
                form_errors[sale_id] = "Debes indicar la fecha del pago."
            elif form_errors.get(sale_id):
                pass
            else:
                all_items_validated = all(item.get("accounting_approved") for item in payment_items) if payment_items else False
                inv = float(invoice_amount or 0) if invoice_amount is not None else 0
                fully_paid = total_paid >= inv if inv > 0 else has_payment_items
                if not invoice_file:
                    status_label = "Factura pendiente"
                elif invoice_file and not has_payment_items:
                    status_label = "Factura subida"
                elif has_payment_items and not all_items_validated and not accounting_checked:
                    status_label = "Comprobante subido"
                elif has_payment_items and (all_items_validated or accounting_checked) and fully_paid:
                    status_label = "Pago validado"
                elif has_payment_items and (all_items_validated or accounting_checked) and not fully_paid:
                    status_label = "Pago parcial"
                else:
                    status_label = "Comprobante subido"

                final_approved = accounting_checked or all_items_validated

                payment_update = {
                    "invoice_number": invoice_number or existing.get("invoice_number"),
                    "invoice_amount": invoice_amount if invoice_amount is not None else existing.get("invoice_amount"),
                    "invoice_due_date": invoice_due_date or existing.get("invoice_due_date"),
                    "invoice_file": invoice_file,
                    "payment_proof_file": None,
                    "payment_amount": total_paid,
                    "payment_date": existing.get("payment_date"),
                    "seller_uploaded_at": existing.get("seller_uploaded_at") or (now if invoice_file else None),
                    "payment_uploaded_at": existing.get("payment_uploaded_at") or (now if has_payment_items else None),
                    "accounting_approved": 1 if final_approved else 0,
                    "accounting_approved_by": actor_role if final_approved else None,
                    "accounting_approved_at": now if final_approved else None,
                    "accounting_comment": accounting_comment or existing.get("accounting_comment"),
                    "status": status_label,
                    "created_at": existing.get("created_at") or now,
                    "updated_at": now,
                }
                upsert_sale_payment(sale_id, payment_update)
                if payment_added:
                    flash(f"Pago de ${payment_item_amount:,.2f} guardado correctamente.", "success")
                return redirect(url_for('pagos.pagos', role=actor_role, sale_id=sale_id, saved=sale_id))

    if selected_sale_id:
        selected_sale = get_sale(selected_sale_id)
        sales = [selected_sale] if selected_sale else []
        payment_map = {}
        if selected_sale:
            payment = get_sale_payment(selected_sale_id)
            if payment:
                payment_map[selected_sale_id] = payment
    else:
        sales = list_sales_page_light(per_page, 0)
        sale_ids = [sale["id"] for sale in sales]
        payment_map = get_sale_payments_for_sales(sale_ids)

    totals_map = get_sale_payment_items_totals([s["id"] for s in sales])
    payment_items_map = {s["id"]: list_sale_payment_items(s["id"]) for s in sales} if sales else {}

    sales_records = []
    for sale in sales:
        payment = payment_map.get(sale["id"], {})
        invoice_file = payment.get("invoice_file")
        invoice_number = payment.get("invoice_number")
        invoice_amount = payment.get("invoice_amount")
        invoice_due_date = payment.get("invoice_due_date")
        accounting_approved = bool(payment.get("accounting_approved"))
        accounting_comment = payment.get("accounting_comment")
        payment_items = payment_items_map.get(sale["id"], [])
        
        try:
            if not payment_items and (payment.get("payment_amount") or 0) > 0:
                insert_sale_payment_item({
                    "sale_id": sale["id"],
                    "payment_amount": payment.get("payment_amount"),
                    "payment_date": payment.get("payment_date"),
                    "payment_proof_file": payment.get("payment_proof_file"),
                    "created_at": payment.get("updated_at") or datetime.utcnow().isoformat(timespec='seconds'),
                })
                payment_items = list_sale_payment_items(sale["id"])
                totals_map[sale["id"]] = payment.get("payment_amount")
        except Exception:
            pass
            
        total_paid = float(totals_map.get(sale["id"], 0) or payment.get("payment_amount") or 0)
        has_payment_items = len(payment_items) > 0
        all_items_validated = all(item.get("accounting_approved") for item in payment_items) if payment_items else False
        inv_amt = float(invoice_amount or 0) if invoice_amount is not None else 0
        fully_paid = total_paid >= inv_amt if inv_amt > 0 else has_payment_items
        if not invoice_file:
            status = {"label": "Factura pendiente", "level": "danger"}
        elif invoice_file and not has_payment_items:
            status = {"label": "Factura subida", "level": "warning"}
        elif has_payment_items and not all_items_validated and not accounting_approved:
            status = {"label": "Comprobante subido", "level": "info"}
        elif has_payment_items and (all_items_validated or accounting_approved) and fully_paid:
            status = {"label": "Pago validado", "level": "success"}
        elif has_payment_items and (all_items_validated or accounting_approved) and not fully_paid:
            status = {"label": "Pago parcial", "level": "warning"}
        else:
            status = {"label": "Comprobante subido", "level": "info"}
            
        sales_records.append({
            "id": sale["id"],
            "sale_number": sale["sale_number"],
            "sale_date": sale["sale_date"],
            "sale_time": sale["sale_time"],
            "customer_name": sale["customer_name"],
            "customer_email": sale.get("customer_email"),
            "seller_name": sale["seller_name"],
            "total_amount": sale["total_amount"],
            "invoice_number": invoice_number,
            "invoice_amount": invoice_amount,
            "invoice_due_date": invoice_due_date,
            "invoice_file": invoice_file,
            "payment_items": payment_items,
            "total_paid": total_paid,
            "accounting_approved": accounting_approved,
            "accounting_comment": accounting_comment,
            "payment_status": status,
            "payment_steps": {
                "invoice": bool(invoice_file),
                "proof": has_payment_items,
                "accounting": accounting_approved,
            },
        })

    if payment_filter and not selected_sale_id:
        sales_records = [
            sale for sale in sales_records
            if sale["payment_status"]["label"].lower() == payment_filter.lower()
        ]

    response = make_response(render_template(
        'pagos.html',
        roles=roles,
        current_role=current_role,
        sales_records=sales_records,
        form_errors=form_errors,
        saved_sale_id=saved_sale_id,
        selected_sale_id=selected_sale_id,
        payment_filter=payment_filter,
    ))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
