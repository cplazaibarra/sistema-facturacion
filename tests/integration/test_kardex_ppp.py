import pytest
from app import app
from db import get_connection, get_product_kardex_history, get_inventory_valuation_summary


@pytest.fixture
def client():
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    old_testing = app.config.get("TESTING", False)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
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
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf
        app.config["TESTING"] = old_testing


@pytest.fixture
def clean_test_product():
    """Crea un producto aislado para testear Kardex y PPP continuo."""
    sku = "TEST-KARDEX-001"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM inventory_movements WHERE product_id IN (SELECT id FROM products WHERE sku = %s)", (sku,))
            cur.execute("DELETE FROM products WHERE sku = %s", (sku,))
            cur.execute(
                """
                INSERT INTO products (sku, name, description, category, product_type, unit_of_measure, cost, is_deleted, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, NOW())
                RETURNING id
                """,
                (sku, "Miel Test Kardex", "Producto para tests", "Materia Prima", "Insumo", "UN", 1000.0)
            )
            prod_id = cur.fetchone()["id"]
            conn.commit()

    yield prod_id

    # Limpieza
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM inventory_movements WHERE product_id = %s", (prod_id,))
            cur.execute("DELETE FROM products WHERE id = %s", (prod_id,))
            conn.commit()


def test_kardex_consecutive_purchases_ppp(clean_test_product):
    """
    Verifica que compras consecutivas a costos distintos ponderen correctamente el PPP:
    1. Entrada 1: 100 un a $1.000 -> Saldo: 100 un, Valor: $100.000, PPP: $1.000
    2. Entrada 2: 50 un a $1.300 -> Saldo: 150 un, Valor: $165.000, PPP: $1.100
    """
    prod_id = clean_test_product
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Entrada 1
            cur.execute(
                """
                INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at, reference_type, reference_id)
                VALUES (%s, 'PURCHASE_RECEIPT', 100, 1000.0, '2026-09-01 10:00:00', 'purchase_order', 999991)
                """,
                (prod_id,)
            )
            # Entrada 2
            cur.execute(
                """
                INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at, reference_type, reference_id)
                VALUES (%s, 'PURCHASE_RECEIPT', 50, 1300.0, '2026-09-02 10:00:00', 'purchase_order', 999992)
                """,
                (prod_id,)
            )
            conn.commit()

    kardex = get_product_kardex_history(prod_id, order_asc=True)
    assert kardex["current_stock"] == 150
    assert kardex["current_ppp"] == 1100.0
    assert kardex["current_inventory_value"] == 165000.0
    assert len(kardex["rows"]) == 2

    row1 = kardex["rows"][0]
    assert row1["balance_qty"] == 100
    assert row1["balance_amount"] == 100000.0
    assert row1["ppp"] == 1000.0

    row2 = kardex["rows"][1]
    assert row2["balance_qty"] == 150
    assert row2["balance_amount"] == 165000.0
    assert row2["ppp"] == 1100.0


def test_kardex_sales_preserve_ppp(clean_test_product):
    """
    Verifica que las salidas por venta consuman al PPP vigente y NO alteren el PPP:
    1. Stock inicial: 100 un a $1.000 -> PPP: $1.000
    2. Salida 1: -40 un -> Saldo: 60 un, Valor: $60.000, PPP: $1.000 (inalterado)
    """
    prod_id = clean_test_product
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at)
                VALUES (%s, 'PURCHASE_RECEIPT', 100, 1000.0, '2026-09-01 10:00:00')
                """,
                (prod_id,)
            )
            cur.execute(
                """
                INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at, reference_type, reference_id)
                VALUES (%s, 'SALE', -40, 0, '2026-09-03 12:00:00', 'sale', 88888)
                """,
                (prod_id,)
            )
            conn.commit()

    kardex = get_product_kardex_history(prod_id, order_asc=True)
    assert kardex["current_stock"] == 60
    assert kardex["current_ppp"] == 1000.0
    assert kardex["current_inventory_value"] == 60000.0

    sale_row = kardex["rows"][1]
    assert sale_row["out_qty"] == 40
    assert sale_row["unit_cost_applied"] == 1000.0
    assert sale_row["out_amount"] == 40000.0
    assert sale_row["balance_qty"] == 60
    assert sale_row["balance_amount"] == 60000.0
    assert sale_row["ppp"] == 1000.0


def test_kardex_view_http_and_filters(client, clean_test_product):
    """
    Verifica que la ruta /productos/<id>/kardex devuelva 200 y renderice
    las etiquetas, montos, PPP y modal de auditoría.
    """
    prod_id = clean_test_product
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at)
                VALUES (%s, 'PURCHASE_RECEIPT', 50, 2000.0, '2026-09-05 09:00:00')
                """,
                (prod_id,)
            )
            conn.commit()

    response = client.get(f'/productos/{prod_id}/kardex', follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Kardex Valorizado" in html
    assert "TEST-KARDEX-001" in html
    assert "Miel Test Kardex" in html
    assert "PPP Actual Vigente" in html
    assert "Saldo Val. ($)" in html
    assert "inspectRow" in html


def test_kardex_centralized_page_all_products(client, clean_test_product):
    """
    Verifica que la página centralizada /kardex sin producto muestre:
    - Tabla consolidada de todos los productos
    - Tarjetas de valor total de inventario y stock físico
    - Selector dropdown para filtrar por producto particular
    """
    response = client.get('/kardex')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Kardex Valorizado / PPP" in html
    assert "Valor Total Inventario Vigente" in html
    assert "Total Unidades en Stock Físico" in html
    assert "Filtrar Producto:" in html
    assert "tabla-kardex-todos" in html
    assert "TEST-KARDEX-001" in html


def test_kardex_centralized_page_specific_product(client, clean_test_product):
    """
    Verifica que la página centralizada /kardex?product_id=<id> filtre y muestre
    la auditoría paso a paso del producto particular con selector y opción de limpiar filtro.
    """
    prod_id = clean_test_product
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at)
                VALUES (%s, 'PURCHASE_RECEIPT', 40, 1800.0, '2026-09-07 11:00:00')
                """,
                (prod_id,)
            )
            conn.commit()

    response = client.get(f'/kardex?product_id={prod_id}')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Kardex Detallado: Miel Test Kardex" in html
    assert "TEST-KARDEX-001" in html
    assert "Limpiar filtro" in html
    assert "PPP Actual Vigente" in html
    assert "1,800.00" in html
    assert "inspectRow" in html


def test_kardex_api_endpoint(client, clean_test_product):
    """
    Verifica que /api/productos/<id>/kardex devuelva JSON estructurado con datos correctos.
    """
    prod_id = clean_test_product
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at)
                VALUES (%s, 'PURCHASE_RECEIPT', 30, 1500.0, '2026-09-06 14:00:00')
                """,
                (prod_id,)
            )
            conn.commit()

    response = client.get(f'/api/productos/{prod_id}/kardex')
    assert response.status_code == 200
    data = response.get_json()
    assert data["product"]["sku"] == "TEST-KARDEX-001"
    assert data["current_stock"] == 30.0
    assert data["current_ppp"] == 1500.0
    assert data["current_inventory_value"] == 45000.0
    assert len(data["rows"]) == 1
    assert data["rows"][0]["audit"]["before"]["qty"] == 0.0
    assert data["rows"][0]["audit"]["after"]["qty"] == 30.0


def test_inventory_general_shows_ppp_and_valuation(client, clean_test_product):
    """
    Verifica que la tabla de inventario general /inventario incluya las columnas PPP y Valor Inventario.
    """
    response = client.get('/inventario')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "PPP Actual" in html
    assert "Valor Inventario" in html
    assert "Valor Total" in html

