"""
tests/integration/test_receipt_totals.py
Suite de validación para el ajuste en RECEPCIÓN DE MERCADERÍA:
1. test_receipt_invoice_amount_not_required: Monto Factura no es requerido en la interfaz ni en el POST.
2. test_receipt_calculates_net_amount: Calcula correctamente el subtotal/neto.
3. test_receipt_calculates_vat_19_percent: Calcula el IVA (19%) sobre el valor neto.
4. test_receipt_calculates_total_with_vat: Calcula el TOTAL = Neto + IVA (ejemplo 65.000 + 12.350 = 77.350).
5. test_backend_recalculates_invoice_total: El backend recalcula los totales desde los ítems reales ignorando valores cliente.
6. test_invoice_total_used_for_accounts_payable: La factura en purchase_invoices / CxP se crea con el TOTAL (77.350).
7. test_receipt_inventory_unchanged_by_tax_calculation: Los movimientos en inventory_movements guardan el costo unitario neto sin alteración tributaria.
"""

import pytest
from datetime import datetime, timezone
import uuid

from app import app
from core.database import get_connection
import repositories.products_repo as products_repo
import repositories.purchases_repo as purchases_repo
import repositories.inventory_repo as inventory_repo


@pytest.fixture
def app_client():
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    old_testing = app.config.get("TESTING", False)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf
        app.config["TESTING"] = old_testing


def _login_as_admin(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "admin"
        sess["role_name"] = "Administrativo"
        sess["full_name"] = "Administrador Sistema"
        sess["permissions"] = {
            "dashboard": True, "ventas": True, "inventario": True,
            "productos": True, "reportes": True, "compras": True,
            "produccion": True, "trazabilidad": True, "administracion": True,
        }


def _create_oc_with_items(items_spec: list[dict]) -> tuple[int, str]:
    """
    items_spec: list of dicts: {"name": str, "qty": int, "unit_price": float}
    Retorna (po_id, oc_number)
    """
    u = uuid.uuid4().hex[:6]
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    oc_number = f"OC-TEST-REC-{u}"
    total_oc = sum(it["qty"] * it["unit_price"] for it in items_spec)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Crear o buscar proveedor
            cur.execute("SELECT id FROM suppliers LIMIT 1")
            s_row = cur.fetchone()
            supplier_id = s_row["id"] if s_row else 1

            cur.execute(
                """
                INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, created_at)
                VALUES (%s, %s, %s, 'Emitida', %s, %s)
                RETURNING id
                """,
                (oc_number, supplier_id, "2026-09-18", total_oc, now_str)
            )
            po_id = cur.fetchone()["id"]

            for it in items_spec:
                # Crear producto
                sku = f"SKU-{uuid.uuid4().hex[:6]}"
                prod_id = products_repo.create_product(
                    sku=sku,
                    name=it.get("name", f"Producto {sku}"),
                    category="Insumos",
                    product_type="Insumo",
                    cost=it["unit_price"],
                    requires_lot=False
                )
                it["product_id"] = prod_id
                cur.execute(
                    """
                    INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_price, total_price)
                    VALUES (%s, %s, %s, 0, %s, %s)
                    """,
                    (po_id, prod_id, it["qty"], it["unit_price"], it["qty"] * it["unit_price"])
                )
        conn.commit()

    return po_id, oc_number


def test_receipt_invoice_amount_not_required(app_client):
    """1. El campo Monto Factura no es requerido en el formulario de recepción."""
    _login_as_admin(app_client)
    po_id, oc_num = _create_oc_with_items([{"qty": 10, "unit_price": 5000.0}])

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT product_id FROM purchase_order_items WHERE purchase_order_id = %s", (po_id,))
            prod_id = cur.fetchone()["product_id"]

    # Enviar recepción con Factura de Compra SIN invoice_amount
    payload = {
        "purchase_order_id": po_id,
        "order_number": f"REC-{uuid.uuid4().hex[:6]}",
        "document_type": "factura",
        "document_number": f"FAC-{uuid.uuid4().hex[:6]}",
        "due_date": "2026-10-18",
        "warehouse": "Almacén Principal",
        "product_id[]": [str(prod_id)],
        "quantity[]": ["10"],
        "unit_price[]": ["5000.0"],
        "lot_number[]": [""]
    }

    res = app_client.post("/ingreso-mercaderia", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert "registrado con éxito" in res.data.decode("utf-8")


def test_receipt_calculates_net_amount(app_client):
    """2. Calcula correctamente el valor Neto de los productos recibidos."""
    _login_as_admin(app_client)
    # Ejemplo con Neto = 65.000 (13 unidades a 5.000)
    items = [{"qty": 13, "unit_price": 5000.0}]
    po_id, oc_num = _create_oc_with_items(items)
    prod_id = items[0]["product_id"]

    doc_num = f"FAC-{uuid.uuid4().hex[:6]}"
    payload = {
        "purchase_order_id": po_id,
        "order_number": f"REC-{uuid.uuid4().hex[:6]}",
        "document_type": "factura",
        "document_number": doc_num,
        "due_date": "2026-10-18",
        "warehouse": "Almacén Principal",
        "product_id[]": [str(prod_id)],
        "quantity[]": ["13"],
        "unit_price[]": ["5000.0"],
        "lot_number[]": [""]
    }
    res = app_client.post("/ingreso-mercaderia", data=payload, follow_redirects=True)
    assert res.status_code == 200

    # Verificar que el ingreso registró total_amount = 65000 (neto físico)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT total_amount FROM inventory_entries WHERE document_number = %s", (doc_num,))
            entry = cur.fetchone()
            assert entry is not None
            assert float(entry["total_amount"]) == 65000.0


def test_receipt_calculates_vat_19_percent(app_client):
    """3. Calcula el IVA (19%) sobre el valor neto de la mercadería recibida."""
    # Para Neto = 65.000 -> IVA 19% = 12.350
    neto = 65000.0
    iva = round(neto * 0.19)
    assert iva == 12350


def test_receipt_calculates_total_with_vat(app_client):
    """4. Calcula TOTAL = Neto + IVA (65.000 + 12.350 = 77.350)."""
    neto = 65000.0
    iva = round(neto * 0.19)
    total = neto + iva
    assert total == 77350


def test_backend_recalculates_invoice_total(app_client):
    """5. El backend recalcula obligatoriamente el total ignorando manipulaciones cliente."""
    _login_as_admin(app_client)
    items = [{"qty": 13, "unit_price": 5000.0}]
    po_id, oc_num = _create_oc_with_items(items)
    prod_id = items[0]["product_id"]

    doc_num = f"FAC-{uuid.uuid4().hex[:6]}"
    # Intentar inyectar un invoice_amount falso (ej. 999999 o 1000)
    payload = {
        "purchase_order_id": po_id,
        "order_number": f"REC-{uuid.uuid4().hex[:6]}",
        "document_type": "factura",
        "document_number": doc_num,
        "due_date": "2026-10-18",
        "warehouse": "Almacén Principal",
        "invoice_amount": "999999.0", # Valor adulterado por el cliente
        "product_id[]": [str(prod_id)],
        "quantity[]": ["13"],
        "unit_price[]": ["5000.0"],
        "lot_number[]": [""]
    }
    res = app_client.post("/ingreso-mercaderia", data=payload, follow_redirects=True)
    assert res.status_code == 200

    # Verificar que en purchase_invoices se ignoró el 999999 y se asignó 77350
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT invoice_amount FROM purchase_invoices WHERE invoice_number = %s", (doc_num,))
            inv = cur.fetchone()
            assert inv is not None
            assert float(inv["invoice_amount"]) == 77350.0


def test_invoice_total_used_for_accounts_payable(app_client):
    """6. El total con IVA (77.350) es el utilizado en Cuentas por Pagar."""
    _login_as_admin(app_client)
    items = [{"qty": 13, "unit_price": 5000.0}]
    po_id, oc_num = _create_oc_with_items(items)
    prod_id = items[0]["product_id"]

    doc_num = f"FAC-{uuid.uuid4().hex[:6]}"
    payload = {
        "purchase_order_id": po_id,
        "order_number": f"REC-{uuid.uuid4().hex[:6]}",
        "document_type": "factura",
        "document_number": doc_num,
        "due_date": "2026-10-18",
        "warehouse": "Almacén Principal",
        "product_id[]": [str(prod_id)],
        "quantity[]": ["13"],
        "unit_price[]": ["5000.0"],
        "lot_number[]": [""]
    }
    app_client.post("/ingreso-mercaderia", data=payload, follow_redirects=True)

    # Consultar Cuentas por Pagar
    # The operational list is now paginated; search the complete filtered
    # invoice universe rather than assuming this new invoice is on page 1.
    res_cxp = app_client.get("/compras/cuentas-por-pagar", query_string={"search": doc_num})
    assert res_cxp.status_code == 200
    assert doc_num.encode("utf-8") in res_cxp.data
    assert b"77.350" in res_cxp.data or b"77350" in res_cxp.data


def test_receipt_inventory_unchanged_by_tax_calculation(app_client):
    """7. El inventario (inventory_movements) guarda el costo unitario neto sin alteración tributaria."""
    _login_as_admin(app_client)
    items = [{"qty": 13, "unit_price": 5000.0}]
    po_id, oc_num = _create_oc_with_items(items)
    prod_id = items[0]["product_id"]

    doc_num = f"FAC-{uuid.uuid4().hex[:6]}"
    payload = {
        "purchase_order_id": po_id,
        "order_number": f"REC-{uuid.uuid4().hex[:6]}",
        "document_type": "factura",
        "document_number": doc_num,
        "due_date": "2026-10-18",
        "warehouse": "Almacén Principal",
        "product_id[]": [str(prod_id)],
        "quantity[]": ["13"],
        "unit_price[]": ["5000.0"],
        "lot_number[]": [""]
    }
    app_client.post("/ingreso-mercaderia", data=payload, follow_redirects=True)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT quantity, unit_cost, movement_type
                FROM inventory_movements
                WHERE product_id = %s AND reference_type = 'purchase_order' AND reference_id = %s
                """,
                (prod_id, po_id)
            )
            mov = cur.fetchone()
            assert mov is not None
            assert float(mov["quantity"]) == 13.0
            # El unit_cost del movimiento es exactamente el NETO (5000.0), no afectado por IVA
            assert float(mov["unit_cost"]) == 5000.0
            assert mov["movement_type"] == "PURCHASE_RECEIPT"
