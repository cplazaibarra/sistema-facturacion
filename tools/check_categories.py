import json
import sqlite3

DB_PATH = r"D:\Desarrollo\clientes\Facturacion-Bodega-miel\data\app.db"

def load_page_data(conn, key):
    row = conn.execute("SELECT json FROM page_data WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    return json.loads(row[0])

def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        categories = load_page_data(conn, "inventory_categories") or []
        descriptions = load_page_data(conn, "inventory_category_descriptions") or {}
        print("Categorias:", categories)
        print("Descripciones:", descriptions)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
