# Informe de Reconciliación de Inventario Real
**Sistema de Facturación / Bodega Miel (ERP Single-Tenant)**  
**Fase 2 — Consistencia y Fuente de Verdad de Inventario**  
**Fecha de Ejecución:** Septiembre 2026  
**Herramienta de Auditoría:** `tools/reconcile_inventory.py` (Modo Read-Only estricto)

---

## 1. Resumen Estadístico General

| Métrica | Valor Numérico | Observación |
| :--- | :---: | :--- |
| **Total SKUs Analizados** | **112** | 111 registrados en catálogo relacional `products` + 1 SKU presente solo en JSON legacy |
| **Productos en Catálogo `products`** | **111** | Productos activos no eliminados |
| **Productos con Algún Stock (> 0)** | **11** | Poseen existencia física en `page_data` o en `lot_stock` |
| **Productos Sin Stock (en ambas fuentes = 0)** | **101** | Catálogo sin existencias físicas |
| **Productos Coincidentes (page_data == lot_stock)** | **0** | Ningún producto con stock coincide exactamente entre ambas fuentes |
| **Productos con Diferencias Cuantitativas** | **11** | 100% de los productos con existencias presentan descalce |
| **Suma de Diferencias Absolutas** | **5.118,00 un.** | Volumen total de unidades desalineadas |
| **Productos Solo en `page_data`** | **9** | Poseen stock en JSON, pero 0 en `lot_stock` |
| **Productos Solo en `lot_stock`** | **2** | Poseen stock en tabla de lotes, pero 0 en `page_data` |

---

## 2. Detalle de Productos con Diferencias y Análisis Causal

A continuación se detalla la evidencia documental e histórica recolectada para cada uno de los 11 productos con discrepancias:

| SKU | Nombre Producto | Stock `page_data` | Stock `lot_stock` | Delta (Page - Lot) | Estado | Causa Probable |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`PRD001`** | Miel Pura 1kg | 450.00 | 0.00 | +450.00 | `ONLY_PAGE_DATA` | **`MIGRACIÓN SQLITE`** / `LEGACY` |
| **`PRD002`** | Miel Pura 500g | 701.00 | 0.00 | +701.00 | `ONLY_PAGE_DATA` | **`COMPRA`** + **`PRODUCCIÓN`** |
| **`PRD003`** | Polen de Abeja 250g | 36.00 | 0.00 | +36.00 | `ONLY_PAGE_DATA` | **`MIGRACIÓN SQLITE`** + **`COMPRA`** |
| **`PRD004`** | Propóleo 30ml | 182.00 | 0.00 | +182.00 | `ONLY_PAGE_DATA` | **`MIGRACIÓN SQLITE`** + **`COMPRA`** |
| **`INS001`** | Miel a Granel (kg) | 1.200.00 | 0.00 | +1.200.00 | `ONLY_PAGE_DATA` | **`LEGACY`** + **`COMPRA`** - **`PRODUCCIÓN`** |
| **`INS002`** | Frasco de Vidrio 500g | 471.00 | 0.00 | +471.00 | `ONLY_PAGE_DATA` | **`LEGACY`** - **`PRODUCCIÓN`** |
| **`INS003`** | Tapa para Frasco | 478.00 | 0.00 | +478.00 | `ONLY_PAGE_DATA` | **`LEGACY`** - **`PRODUCCIÓN`** |
| **`INS-ENV-003`** | Envase 500 g | 500.00 | 0.00 | +500.00 | `ONLY_PAGE_DATA` | **`COMPRA`** |
| **`INS-ETQ-002`** | Etiqueta Envase 500 g PET | 500.00 | 0.00 | +500.00 | `ONLY_PAGE_DATA` | **`COMPRA`** |
| **`2222`** | MIEL MATERIA PRIMA | 0.00 | 300.00 | -300.00 | `ONLY_LOT_STOCK` | **`INCONSISTENCIA`** / **`COMPRA`** |
| **`INS-MPR-001`** | Materia Prima Miel | 0.00 | 300.00 | -300.00 | `ONLY_LOT_STOCK` | **`COMPRA`** |

---

## 3. Reconstrucción Causal por Producto

### 3.1 Grupo 1: Semilla Inicial y Migración SQLite (`PRD001`, `PRD003`, `PRD004`)
- **`PRD001` (Miel Pura 1kg):**
  - En `db.py:DEFAULT_DATA["inventory_items"]` figuraba con stock inicial sembrado de `450.00` unidades.
  - No existen compras ni órdenes de producción en la base de datos relacional para este SKU.
  - Causa: **Saldo Inicial Migración SQLite / Legacy**.
- **`PRD003` (Polen de Abeja 250g):**
  - Semilla inicial: `35.00` unidades.
  - Ingresos de compra documentados: Entrada #1 (+2), Entrada #8 (+1), Entrada #21 (+1) = +4 unidades recibidas sin lote.
  - Ventas o rebajas registradas: 3 unidades en pruebas de cotización/venta.
  - Saldo en `page_data`: `36.00` unidades. En `lot_stock`: `0.00`.
  - Causa: **Saldo Inicial + Compras sin Lote**.
- **`PRD004` (Propóleo 30ml):**
  - Semilla inicial: `180.00` unidades.
  - Ingresos de compra documentados: Entrada #1 (+8), #2 (+13), #3 (+20), #8 (+10), #10 (+4), #11 (+2), #12 (+1), #21 (+2) = +60 unidades recibidas sin lote.
  - Saldo en `page_data`: `182.00` unidades (refleja consumo en pruebas de venta). En `lot_stock`: `0.00`.
  - Causa: **Saldo Inicial + Compras sin Lote**.

### 3.2 Grupo 2: Interacción Compras y Producción (`PRD002`, `INS001`, `INS002`, `INS003`)
- **`PRD002` (Miel Pura 500g):**
  - Semilla inicial: `680.00` unidades.
  - Ingresos por compras: Entrada #4 (+100), #8 (+20), #10 (+1), #21 (+3) = +124 unidades.
  - Ingresos por Producción finalizada: OT-00001 (+11), OT-00004 (+2), OT-00005 (+2), OT-00006 (+3) = +18 unidades.
  - Descuentos por ventas realizadas: VTA-00030, 31, 32, 41, 43 (-121 unidades aprox).
  - Saldo en `page_data`: `701.00` unidades. En `lot_stock`: `0.00`.
  - Causa: **Interacción de compras y OTs sin asignación de lote físico**.
- **`INS001` (Miel a Granel):**
  - Stock en `page_data`: `1.200.00` kg.
  - Ingresos por compras: Entrada #18 (+380 kg).
  - Consumo en OTs finalizadas: OT-00001 (-110), OT-00004 (-20), OT-00005 (-20), OT-00006 (-30) = -180 kg.
  - Causa: **Saldo Inicial Base (1.000 kg) + Compra (380 kg) - Consumos OTs (180 kg) = 1.200 kg**. `lot_stock` en 0 porque la compra #18 no traía número de lote.
- **`INS002` (Frasco de Vidrio 500g) e `INS003` (Tapa para Frasco):**
  - Stock en `page_data`: Frascos `471.00`, Tapas `478.00`.
  - Saldo base inicial: 500 unidades.
  - Consumos en OTs: OT-00001 (-11), OT-00004 (-2), OT-00005 (-2 - 2 adic), OT-00006 (-3 - 1 adic).
  - Causa: **Consumos de producción deducidos exclusivamente en `page_data`**.

### 3.3 Grupo 3: Compras Recientes sin Lote (`INS-ENV-003`, `INS-ETQ-002`)
- **`INS-ENV-003` (Envase 500 g):**
  - Ingresos: Entrada #19 (FAC-701-A, +300), Entrada #20 (FAC-702-B, +200) = +500 unidades.
  - Ambos ingresos llegaron con `lot_number = ''`.
  - Consecuencia: Se sumaron a `page_data` (+500), pero se omitieron en `lot_stock` (0).
- **`INS-ETQ-002` (Etiqueta Envase 500 g PET):**
  - Ingresos: Entrada #19 (+200), Entrada #20 (+300) = +500 unidades.
  - Ambos ingresos sin lote. Stock en `page_data`: 500, en `lot_stock`: 0.

### 3.4 Grupo 4: Existencia Exclusiva en `lot_stock` (`2222`, `INS-MPR-001`)
- **`2222` (MIEL MATERIA PRIMA):**
  - Entrada #13 ('prueba lote', 2026-09-05) con Lote `202601` por 300 unidades.
  - Se guardó en `lot_stock` (300 un.).
  - En `page_data`, el ítem con código '2222' figuraba como 'PF-test1' con stock `0.0`. Hubo colisión de SKU entre un insumo y un producto terminado de prueba.
  - Consecuencia: `lot_stock` tiene 300 unidades físicas reales, `page_data` tiene 0.0.
- **`INS-MPR-001` (Materia Prima Miel):**
  - Entrada #14 ('ejemplo', 2026-09-07) con Lote `202602` por 300 unidades.
  - Se guardó en `lot_stock` (300 un.).
  - El producto 'INS-MPR-001' no existía en el JSON `page_data.inventory_items` al momento de la recepción y la rutina no lo añadió al JSON por omisión de catálogo.
  - Consecuencia: `lot_stock` tiene 300 unidades físicas reales, `page_data` tiene 0.0.

---

## 4. Conclusiones Técnicas Fundamentales

1. **`lot_stock` NO es actualmente suficiente para ser la fuente de verdad única de todo el ERP:**
   - Solo 2 de las 20 recepciones históricas ingresaron con número de lote.
   - 9 de los 11 productos con existencia física no tienen registros en `lot_stock` porque sus recepciones no llevaban lote o provienen de saldos iniciales y órdenes de trabajo.
2. **`page_data.inventory_items` es frágil y sufre de desalineación:**
   - No tiene trazabilidad de auditoría.
   - Padece colisiones de SKUs ('2222').
   - No es atómico ni transaccional.
3. **Se requiere una fuente de verdad relacional universal:**
   - Una tabla relacional de movimientos (Ledger / Kardex) capaz de registrar entradas por compras (con o sin lote), salidas por ventas, consumo de insumos de producción, alta de productos terminados, y ajustes de inventario con trazabilidad total.
