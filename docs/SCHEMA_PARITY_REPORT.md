# REPORTE DE PARIDAD DE ESQUEMA (FASE 4)

**Fecha:** 2026-09-15  
**Resultado:** `SCHEMA_PARITY = PASS`  
**Comparación:** Base de datos activa (`facturacion`) vs Base de datos limpia migrada desde cero (`facturacion_fresh_test`).

---

## 1. Alcance de la Validación

Se ejecutó la herramienta de inspección automatizada `tools/compare_schema.py`, la cual evalúa:
1. **Existencia y Nombre de Tablas:** Coincidencia exacta de las 30 tablas base + tabla de control `schema_migrations`.
2. **Columnas y Tipos de Datos:** Coincidencia del 100% de nombres de columnas y tipos de datos de PostgreSQL (`integer`, `text`, `double precision`, `boolean`, `timestamp with time zone`, etc.).
3. **Restricciones CHECK:** Verificación de las reglas invariantes de cantidad y saldo no negativo.
4. **Claves Foráneas (Foreign Keys):** Verificación de integridad referencial.
5. **Secuencias:** Verificación de existencia de las 30 secuencias del sistema, incluyendo los correlativos atómicos de negocio (`purchase_order_number_seq`, `sales_number_seq`, `production_order_number_seq`).

---

## 2. Detalle de Paridad por Componente

| Componente | Base de Referencia (`facturacion`) | Base Limpia Migrada (`facturacion_fresh_test`) | Estado |
|---|---|---|---|
| Tablas Base | 30 | 30 | **IDÉNTICO** |
| Columnas Totales | 215 | 215 | **IDÉNTICO** |
| Secuencias | 30 | 30 | **IDÉNTICO** |
| Restricciones CHECK Invariantes | 7 | 7 | **IDÉNTICO** |
| Claves Foráneas | 30 | 30 | **IDÉNTICO** |
| Tabla de Control | `schema_migrations` (v1-v5) | `schema_migrations` (v1-v5) | **IDÉNTICO** |

---

## 3. Conclusión

El esquema generado por las 5 migraciones SQL (`migrations/000001` a `migrations/000005`) replica exactamente la estructura y restricciones requeridas para el funcionamiento integral del ERP sin depender de scripts manuales o historial previo.
