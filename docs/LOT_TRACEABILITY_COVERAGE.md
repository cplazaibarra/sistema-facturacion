# Reporte de Cobertura Histórica de Trazabilidad de Lotes (Fase 5B)

**Fecha de Análisis:** 15 de Septiembre de 2026  
**Sistema:** ERP Facturación & Gestión de Negocio  
**Herramienta de Auditoría:** `tools/backfill_lot_genealogy.py`

---

## 1. Resumen de Cobertura Histórica

| Entidad / Proceso | Total Histórico | Con Lote Exacto (EXACT) | Parcial (INFERRED) | Sin Lote / No Reconstruible (UNKNOWN) | % Trazabilidad Exacta |
|---|---|---|---|---|---|
| **Recepciones de Mercadería (`inventory_entry_items`)** | 33 | 2 | 0 | 31 | **6.06%** |
| **Órdenes de Trabajo (`production_orders`)** | 6 | 0 | 0 | 6 | **0.00%** |
| **Ventas Realizadas (`sales`)** | 63 | 0 | 0 | 63 | **0.00%** |

---

## 2. Detalle de Registros Históricos Verificados (EXACT)

Los únicos registros históricos con número de lote formalmente especificado corresponden a:
1. **Lote `202601`:**
   - **Producto:** `MIEL MATERIA PRIMA` (ID 13, SKU `2222`).
   - **Cantidad Recibida:** 300 unidades.
   - **Recepción ID:** 13 (Fecha: `2026-09-05`, Documento: `prueba lote`).
   - **Orden de Compra ID:** 10.
   - **Proveedor ID:** 2.
   - **Bodega:** `Almacén Principal`.
   - **Saldo Actual en `lot_stock`:** 300 unidades.
2. **Lote `202602`:**
   - **Producto:** `Materia Prima Miel` (ID 14, SKU `INS-MPR-001`).
   - **Cantidad Recibida:** 300 unidades.
   - **Recepción ID:** 14 (Fecha: `2026-09-07`, Documento: `ejemplo`).
   - **Orden de Compra ID:** 11.
   - **Proveedor ID:** 3.
   - **Bodega:** `Almacén Principal`.
   - **Saldo Actual en `lot_stock`:** 300 unidades.

Ambos lotes fueron incorporados a la tabla maestra `lots` y vinculados bidireccionalmente con `lot_stock` e `inventory_entry_items`.

---

## 3. Información que NO Pudo Reconstruirse (UNKNOWN)

Siguiendo el principio de **integridad estricta**:
- **31 líneas de recepción:** Fueron ingresadas con cadena vacía (`lot_number = ''`) antes de que los productos respectivos requirieran lote o sin registro de lote en la guía de despacho.
- **6 órdenes de trabajo (OT-00001 a OT-00006):** Fueron finalizadas sin asociar lotes de insumos consumidos ni asignar lote a los productos terminados. No existen registros de pesaje ni bitácora de lote para estas OTs previas.
- **63 ventas:** Fueron procesadas antes de la existencia de `sale_lot_movements` vinculada a `lots`.

**Regla de Oro Aplicada:** Cero invención de datos. No se asignaron lotes ficticios ni suposiciones retrospectivas para hacer cuadrar la historia.

---

## 4. Política a Partir de Fase 5B

Para toda operación creada a partir de la entrada en vigencia de Fase 5B:
- Si `products.requires_lot = TRUE`:
  - **Recepción:** El número de lote es obligatorio y se registra en `lots`.
  - **Producción:** El lote exacto consumido de cada insumo es obligatorio y se registra en `production_lot_consumptions`.
  - **Producto Terminado:** Toda OT genera un lote trazable registrado en `production_lot_outputs`.
  - **Venta:** La venta consume lotes exactos y registra en `sale_lot_movements` con `lot_id`.
- La cobertura de trazabilidad a partir de Fase 5B para productos con lote es del **100% garantizado**.
