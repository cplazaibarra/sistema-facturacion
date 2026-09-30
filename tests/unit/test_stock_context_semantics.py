from services.stock_context import calculate_stock_balance, get_reserved_stock_by_sku


def test_stock_balance_without_reservations():
    assert calculate_stock_balance(12) == {
        "physical_stock": 12.0,
        "reserved_stock": 0.0,
        "physical_reserved_stock": 0.0,
        "available_stock": 12.0,
    }


def test_stock_balance_keeps_reserved_units_inside_physical_stock():
    balance = calculate_stock_balance(100, 10)
    assert balance == {"physical_stock": 100.0, "reserved_stock": 10.0,
                       "physical_reserved_stock": 10.0, "available_stock": 90.0}
    assert balance["physical_stock"] == balance["available_stock"] + balance["reserved_stock"]


def test_stock_balance_keeps_full_demand_when_reservation_exceeds_physical():
    assert calculate_stock_balance(0, 0)["available_stock"] == 0
    balance = calculate_stock_balance(5, 8)
    assert balance == {"physical_stock": 5.0, "reserved_stock": 8.0,
                       "physical_reserved_stock": 5.0, "available_stock": 0.0}


def test_reservations_resolve_identity_then_exact_legacy_and_flag_ambiguous(monkeypatch):
    class Cursor:
        query = ""

        def execute(self, query, *_):
            self.query = query

        def fetchall(self):
            if "FROM products p" in self.query:
                return [
                    {"sku": "A", "physical_stock": 2},
                    {"sku": "B", "physical_stock": 7},
                    {"sku": "C", "physical_stock": 5},
                ]
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr("services.stock_context.get_connection", lambda: Connection())
    products = [
        {"id": 1, "sku": "A", "name": "Producto Uno"},
        {"id": 2, "sku": "B", "name": "Producto Dos"},
        {"id": 3, "sku": "C", "name": "Producto Uno Grande"},
    ]
    diagnostics = []
    result = get_reserved_stock_by_sku(products, [{"id": 10, "products": [
        {"product_id": 1, "product_name": "ambiguo Producto", "quantity": 2},
        {"sku": "B", "product_name": "irrelevante", "quantity": 3},
        {"product_name": "Producto Dos", "quantity": 4},
        {"product_name": "Uno Grand", "quantity": 5},
        {"product_name": "producto", "quantity": 6},
    ]}], diagnostics)
    assert result == {"A": 2.0, "B": 7.0, "C": 5.0}
    assert any(row["code"] == "RESERVA_AMBIGUA" for row in diagnostics)
    summary = next(row for row in diagnostics if row["code"] == "RESERVA_RESOLUCION_RESUMEN")
    assert summary["matches"] == {
        "product_id": 1, "sku_exact": 1, "name_exact": 1,
        "name_partial_legacy": 1, "unmatched": 1,
    }


def test_sale_with_two_payments_is_read_once_for_reservation(monkeypatch):
    from repositories import sales_repo

    class Cursor:
        query = ""

        def execute(self, query, *_):
            self.query = query

        def fetchall(self):
            # LATERAL selects one deterministic legacy payment row per sale.
            return [{"id": 10, "sale_number": "VTA-10", "products_json":
                     '[{"product_id": 1, "quantity": 7}]'}]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    cursor = Cursor()
    class Connection:
        def cursor(self):
            return cursor

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(sales_repo, "get_connection", lambda: Connection())
    sales = sales_repo.list_sales({"status": "Pendiente"})
    assert len(sales) == 1
    assert "LEFT JOIN LATERAL" in cursor.query
    assert "ORDER BY id DESC" in cursor.query and "LIMIT 1" in cursor.query

    class ReservationCursor:
        query = ""

        def execute(self, query, *_):
            self.query = query

        def fetchall(self):
            if "FROM products p" in self.query:
                return [{"sku": "SKU-1", "physical_stock": 10}]
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class ReservationConnection:
        def cursor(self):
            return ReservationCursor()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr("services.stock_context.get_connection", lambda: ReservationConnection())
    product = {"id": 1, "sku": "SKU-1", "name": "Producto Uno"}
    assert get_reserved_stock_by_sku([product], sales) == {"SKU-1": 7.0}


def test_already_discounted_pending_sale_is_not_reserved_twice(monkeypatch):
    class Cursor:
        query = ""

        def execute(self, query, *_):
            self.query = query

        def fetchall(self):
            if "FROM sale_items" in self.query:
                return [{"sale_id": 42}]
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    cursor = Cursor()

    class Connection:
        def cursor(self):
            return cursor

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr("services.stock_context.get_connection", lambda: Connection())
    product = {"id": 60, "sku": "PT-CLA-001", "name": "Miel de Ulmo 1 Kg PET"}
    pending_sale = {"id": 42, "products": [{"product_id": 60, "quantity": 10}]}

    assert get_reserved_stock_by_sku([product], [pending_sale]) == {}


def test_out_of_stock_pending_sale_remains_reserved_demand(monkeypatch):
    class Cursor:
        query = ""

        def execute(self, query, *_):
            self.query = query

        def fetchall(self):
            if "FROM products p" in self.query:
                return [{"sku": "SKU-EMPTY", "physical_stock": 0}]
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    cursor = Cursor()

    class Connection:
        def cursor(self):
            return cursor

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr("services.stock_context.get_connection", lambda: Connection())
    product = {"id": 61, "sku": "SKU-EMPTY", "name": "Producto sin stock"}
    pending_sale = {"id": 99, "products": [{"product_id": 61, "quantity": 1}]}
    assert get_reserved_stock_by_sku([product], [pending_sale]) == {"SKU-EMPTY": 1.0}
    assert calculate_stock_balance(0, 1) == {
        "physical_stock": 0.0,
        "reserved_stock": 1.0,
        "physical_reserved_stock": 0.0,
        "available_stock": 0.0,
    }
