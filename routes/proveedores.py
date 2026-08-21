from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from datetime import datetime
from db import (
    list_suppliers,
    get_supplier,
    insert_supplier,
    update_supplier,
    delete_supplier,
    list_supplier_contacts,
    get_supplier_contact,
    insert_supplier_contact,
    update_supplier_contact,
    delete_supplier_contact
)

proveedores_bp = Blueprint('proveedores', __name__)

@proveedores_bp.route('/api/proveedores/crear', methods=['POST'])
def api_crear_proveedor():
    """API para crear proveedor rápido vía AJAX"""
    data = request.get_json() or {}
    name = (data.get('name') or request.form.get('name') or '').strip()
    description = (data.get('description') or request.form.get('description') or '').strip()
    website = (data.get('website') or request.form.get('website') or '').strip()

    if not name:
        return jsonify({"status": "error", "message": "El nombre del proveedor es obligatorio"}), 400

    supplier = {
        "name": name,
        "description": description,
        "website": website,
        "created_at": datetime.utcnow().isoformat(timespec='seconds'),
    }

    supplier_id = insert_supplier(supplier)
    return jsonify({
        "status": "ok",
        "supplier": {
            "id": supplier_id,
            "name": name,
            "description": description,
            "website": website
        }
    })

@proveedores_bp.route('/proveedores', methods=['GET', 'POST'])
def proveedores():
    """Gestión de proveedores"""
    if request.method == 'POST':
        supplier = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "website": request.form.get('website', '').strip(),
            "created_at": datetime.utcnow().isoformat(timespec='seconds'),
        }

        if supplier["name"]:
            insert_supplier(supplier)

        return redirect(url_for('proveedores.proveedores'))

    suppliers = list_suppliers()
    return render_template('proveedores.html', suppliers=suppliers)

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
        supplier = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "website": request.form.get('website', '').strip(),
        }

        if supplier["name"]:
            update_supplier(supplier_id, supplier)

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
        "created_at": datetime.utcnow().isoformat(timespec='seconds'),
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
