from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from datetime import datetime, timezone
from db import (
    list_suppliers,
    get_supplier,
    get_supplier_by_rut,
    insert_supplier,
    update_supplier,
    delete_supplier,
    list_supplier_contacts,
    get_supplier_contact,
    insert_supplier_contact,
    update_supplier_contact,
    delete_supplier_contact,
    format_payment_terms,
)
from core.utils import (
    VALID_PAYMENT_TERMS,
    DEFAULT_PAYMENT_TERMS,
    normalize_rut_str,
    validate_chilean_rut,
    format_chilean_rut,
    is_valid_email,
)
from security import require_permission

proveedores_bp = Blueprint('proveedores', __name__)


@proveedores_bp.before_request
def _require_inventory_permission_for_suppliers():
    """Supplier master data belongs to purchasing, not general authenticated access."""
    @require_permission('inventario')
    def _authorized():
        return None
    return _authorized()

@proveedores_bp.route('/api/proveedores/crear', methods=['POST'])
def api_crear_proveedor():
    """
    API para crear proveedor completo (desde modal de OC o AJAX).
    Valida RUT chileno, unicidad, email y términos de pago.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    raw_rut = (data.get('rut') or '').strip()
    raw_dv = (data.get('dv') or '').strip()
    name = (data.get('name') or data.get('razon_social') or '').strip()
    razon_social = (data.get('razon_social') or name).strip()
    nombre_fantasia = (data.get('nombre_fantasia') or data.get('fantasy_name') or name).strip()
    if not name and razon_social:
        name = razon_social
    elif not razon_social and name:
        razon_social = name

    giro = (data.get('giro') or '').strip()
    direccion = (data.get('direccion') or '').strip()
    comuna = (data.get('comuna') or '').strip()
    ciudad = (data.get('ciudad') or '').strip()
    contacto_nombre = (data.get('contacto') or data.get('contact_name') or '').strip()
    phone = (data.get('phone') or data.get('telefono') or '').strip()
    email = (data.get('email') or '').strip()
    website = (data.get('website') or '').strip()
    description = (data.get('description') or data.get('observaciones') or '').strip()
    default_payment_terms = (data.get('default_payment_terms') or data.get('payment_terms') or DEFAULT_PAYMENT_TERMS).strip().upper()
    if default_payment_terms not in VALID_PAYMENT_TERMS:
        default_payment_terms = DEFAULT_PAYMENT_TERMS

    # 1. Validar nombre / razón social
    if not name and not razon_social:
        return jsonify({
            "status": "error",
            "field": "name",
            "message": "La Razón Social o Nombre del proveedor es obligatorio."
        }), 400

    # 2. Validar RUT
    if not raw_rut:
        return jsonify({
            "status": "error",
            "field": "rut",
            "message": "El RUT del proveedor es obligatorio."
        }), 400

    is_valid, formatted_rut, rut_err = validate_chilean_rut(raw_rut, raw_dv)
    if not is_valid:
        return jsonify({
            "status": "error",
            "field": "rut",
            "message": rut_err
        }), 400

    # 3. Validar Email si se ingresó
    if email and not is_valid_email(email):
        return jsonify({
            "status": "error",
            "field": "email",
            "message": "El correo electrónico no tiene un formato válido (ej: contacto@proveedor.cl)."
        }), 400

    # 4. Verificar duplicados por RUT
    existing = get_supplier_by_rut(formatted_rut)
    if existing:
        return jsonify({
            "status": "duplicate",
            "field": "rut",
            "message": f"Ya existe un proveedor registrado con este RUT: {existing['name']}",
            "supplier": {
                "id": existing["id"],
                "name": existing["name"],
                "razon_social": existing.get("razon_social") or existing["name"],
                "rut": existing.get("rut") or formatted_rut,
                "dv": existing.get("dv") or (formatted_rut.split('-')[-1] if '-' in formatted_rut else ''),
                "default_payment_terms": existing.get("default_payment_terms") or DEFAULT_PAYMENT_TERMS,
                "default_payment_terms_formatted": format_payment_terms(existing.get("default_payment_terms"))
            }
        }), 409

    # Extraer DV final
    _, final_dv = normalize_rut_str(formatted_rut)

    supplier_payload = {
        "name": name,
        "razon_social": razon_social,
        "rut": formatted_rut,
        "dv": final_dv,
        "giro": giro,
        "direccion": direccion,
        "comuna": comuna,
        "ciudad": ciudad,
        "email": email,
        "phone": phone,
        "tipo_compra": "Del Giro",
        "description": description,
        "website": website,
        "default_payment_terms": default_payment_terms,
        "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }

    supplier_id = insert_supplier(supplier_payload)

    # Si se especificó nombre de contacto, crearlo en supplier_contacts
    if contacto_nombre:
        contact_payload = {
            "supplier_id": supplier_id,
            "name": contacto_nombre,
            "phone": phone,
            "email": email,
            "position": "Contacto Comercial",
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        insert_supplier_contact(contact_payload)

    return jsonify({
        "status": "ok",
        "message": "Proveedor registrado exitosamente.",
        "supplier": {
            "id": supplier_id,
            "name": name,
            "razon_social": razon_social,
            "rut": formatted_rut,
            "dv": final_dv,
            "direccion": direccion,
            "comuna": comuna,
            "ciudad": ciudad,
            "contacto": contacto_nombre,
            "phone": phone,
            "email": email,
            "default_payment_terms": default_payment_terms,
            "default_payment_terms_formatted": format_payment_terms(default_payment_terms)
        }
    })

@proveedores_bp.route('/api/proveedores/<int:supplier_id>')
def api_get_proveedor(supplier_id):
    """API para consultar datos básicos de un proveedor (ej: forma de pago predeterminada)."""
    supplier = get_supplier(supplier_id)
    if not supplier:
        return jsonify({"error": "Proveedor no encontrado"}), 404
    raw_terms = supplier.get("default_payment_terms") or "NET_30"
    return jsonify({
        "id": supplier["id"],
        "name": supplier["name"],
        "rut": supplier.get("rut"),
        "dv": supplier.get("dv"),
        "default_payment_terms": raw_terms,
        "default_payment_terms_formatted": format_payment_terms(raw_terms)
    })

@proveedores_bp.route('/proveedores', methods=['GET', 'POST'])
def proveedores():
    """Gestión de proveedores"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        razon_social = request.form.get('razon_social', '').strip() or name
        raw_rut = request.form.get('rut', '').strip()
        raw_dv = request.form.get('dv', '').strip().upper()
        email = request.form.get('email', '').strip()
        default_payment_terms = request.form.get('default_payment_terms', 'NET_30').strip().upper()

        if not name:
            flash("El nombre o razón social del proveedor es obligatorio.", "danger")
            return redirect(url_for('proveedores.proveedores'))

        if raw_rut:
            is_valid, formatted_rut, rut_err = validate_chilean_rut(raw_rut, raw_dv)
            if not is_valid:
                flash(rut_err, "danger")
                return redirect(url_for('proveedores.proveedores'))

            existing = get_supplier_by_rut(formatted_rut)
            if existing:
                flash(f"Ya existe un proveedor registrado con este RUT: {existing['name']}.", "warning")
                return redirect(url_for('proveedores.proveedores'))
            _, final_dv = normalize_rut_str(formatted_rut)
        else:
            formatted_rut = None
            final_dv = None

        if email and not is_valid_email(email):
            flash("El correo electrónico ingresado no tiene un formato válido.", "danger")
            return redirect(url_for('proveedores.proveedores'))

        supplier = {
            "name": name or razon_social,
            "razon_social": razon_social,
            "rut": formatted_rut,
            "dv": final_dv,
            "giro": request.form.get('giro', '').strip(),
            "direccion": request.form.get('direccion', '').strip(),
            "comuna": request.form.get('comuna', '').strip(),
            "ciudad": request.form.get('ciudad', '').strip(),
            "email": email,
            "phone": request.form.get('phone', '').strip(),
            "tipo_compra": request.form.get('tipo_compra', 'Del Giro').strip(),
            "description": request.form.get('description', '').strip(),
            "website": request.form.get('website', '').strip(),
            "default_payment_terms": default_payment_terms,
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }

        insert_supplier(supplier)
        flash("Proveedor registrado exitosamente.", "success")
        return redirect(url_for('proveedores.proveedores'))

    from db import get_suppliers_paginated

    search_query = request.args.get('search', '').strip()

    try:
        current_page = int(request.args.get('page', 1))
        if current_page < 1:
            current_page = 1
    except (ValueError, TypeError):
        current_page = 1

    try:
        per_page = int(request.args.get('per_page', 25))
        if per_page not in (25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    paginated = get_suppliers_paginated(
        page=current_page,
        per_page=per_page,
        search=search_query
    )

    return render_template(
        'proveedores.html',
        suppliers=paginated["items"],
        current_page=paginated["page"],
        per_page=paginated["per_page"],
        total_pages=paginated["total_pages"],
        total_suppliers=paginated["total"],
        search_query=search_query
    )

@proveedores_bp.route('/proveedores/<int:supplier_id>')
def ver_proveedor(supplier_id):
    """Ver detalles de un proveedor y sus contactos"""
    supplier = get_supplier(supplier_id)
    contacts = list_supplier_contacts(supplier_id)
    return render_template('ver_proveedor.html', supplier=supplier, contacts=contacts)

@proveedores_bp.route('/proveedores/<int:supplier_id>/editar', methods=['GET', 'POST'])
def editar_proveedor(supplier_id):
    """Editar un proveedor"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        razon_social = request.form.get('razon_social', '').strip() or name
        default_payment_terms = request.form.get('default_payment_terms', 'NET_30').strip().upper()
        supplier = {
            "name": name or razon_social,
            "razon_social": razon_social,
            "rut": request.form.get('rut', '').strip(),
            "dv": request.form.get('dv', '').strip().upper(),
            "giro": request.form.get('giro', '').strip(),
            "direccion": request.form.get('direccion', '').strip(),
            "comuna": request.form.get('comuna', '').strip(),
            "ciudad": request.form.get('ciudad', '').strip(),
            "email": request.form.get('email', '').strip(),
            "phone": request.form.get('phone', '').strip(),
            "tipo_compra": request.form.get('tipo_compra', 'Del Giro').strip(),
            "description": request.form.get('description', '').strip(),
            "website": request.form.get('website', '').strip(),
            "default_payment_terms": default_payment_terms,
        }

        if supplier["name"]:
            update_supplier(supplier_id, supplier)
            flash("Cambios guardados con éxito", "success")

        return redirect(url_for('proveedores.editar_proveedor', supplier_id=supplier_id))

    supplier = get_supplier(supplier_id)
    contacts = list_supplier_contacts(supplier_id)
    return render_template('editar_proveedor.html', supplier=supplier, contacts=contacts)

@proveedores_bp.route('/proveedores/<int:supplier_id>/eliminar', methods=['POST'])
def eliminar_proveedor(supplier_id):
    """Eliminar un proveedor"""
    delete_supplier(supplier_id)
    return redirect(url_for('proveedores.proveedores'))

@proveedores_bp.route('/proveedores/<int:supplier_id>/contactos', methods=['POST'])
def agregar_contacto(supplier_id):
    """Agregar contacto a un proveedor"""
    contact = {
        "supplier_id": supplier_id,
        "name": request.form.get('name', '').strip(),
        "phone": request.form.get('phone', '').strip(),
        "email": request.form.get('email', '').strip(),
        "position": request.form.get('position', '').strip(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }

    if contact["name"]:
        insert_supplier_contact(contact)

    return_to = request.form.get('return_to', 'ver')
    if return_to == 'editar':
        return redirect(url_for('proveedores.editar_proveedor', supplier_id=supplier_id))
    return redirect(url_for('proveedores.ver_proveedor', supplier_id=supplier_id))

@proveedores_bp.route('/contactos/<int:contact_id>/editar', methods=['GET', 'POST'])
def editar_contacto(contact_id):
    """Editar contacto de proveedor"""
    if request.method == 'POST':
        contact = {
            "name": request.form.get('name', '').strip(),
            "phone": request.form.get('phone', '').strip(),
            "email": request.form.get('email', '').strip(),
            "position": request.form.get('position', '').strip(),
        }

        current_contact = get_supplier_contact(contact_id)
        update_supplier_contact(contact_id, contact)

        return redirect(url_for('proveedores.ver_proveedor', supplier_id=current_contact['supplier_id']))

    contact = get_supplier_contact(contact_id)
    return render_template('editar_contacto.html', contact=contact)

@proveedores_bp.route('/contactos/<int:contact_id>/eliminar', methods=['POST'])
def eliminar_contacto(contact_id):
    """Eliminar contacto de proveedor"""
    contact = get_supplier_contact(contact_id)
    supplier_id = contact['supplier_id']
    delete_supplier_contact(contact_id)
    return redirect(url_for('proveedores.ver_proveedor', supplier_id=supplier_id))
