# Informe de Auditoría de Código Legacy (Fase 5)

**Fecha de Análisis:** 15 de Septiembre de 2026  
**Sistema:** ERP Facturación & Gestión de Negocio  

---

## 1. Categorización de Bloques Legacy

El código legacy se clasifica bajo cuatro directivas taxonómicas:
- **`ACTIVE`**: Código actualmente en uso operacional primario.
- **`COMPATIBILITY`**: Capas de adaptación requeridas para mantener compatibilidad con versiones previas, rutas antiguas o contratos de templates sin interrumpir el servicio.
- **`UNUSED_CONFIRMED`**: Funciones o fragmentos que han sido completamente superados y no son referenciados ni por rutas ni por tests.
- **`UNKNOWN`**: Fragmentos cuya dependencia no es inmediatamente evidente en el AST y requieren monitoreo.

---

## 2. Inventario de Componentes y Bloques Legacy

| Componente / Archivo | Bloque / Función | Clasificación | Justificación y Estado |
|---|---|---|---|
| `db.py` | `db.py` Facade Re-exports | `COMPATIBILITY` | Permite que todos los controladores existentes importen funciones sin rotura abrupta. |
| `repositories/legacy_repo.py` | `get_page_data`, `set_page_data` | `COMPATIBILITY` | Mantiene el acceso a claves de UI y sincronización dual-write de inventario. |
| `repositories/legacy_repo.py` | `list_sales_entries`, `insert_sales_entry` | `COMPATIBILITY` | Histórico de entradas de ventas heredado de la primera versión SQLite. |
| `repositories/inventory_repo.py` | `get_stock_with_dual_read` | `COMPATIBILITY` | Monitorea la consistencia entre `inventory_items` (legacy) y `inventory_movements` (oficial). |
| `repositories/inventory_repo.py` | Dual-write en `discount_stock_for_sale` | `COMPATIBILITY` | Descuenta tanto en Kardex relacional como en `page_data` para proteger templates legacy. |
| `core/utils.py` | `normalize_rut_str` | `ACTIVE` | Normalización canónica de RUT chileno (cuerpo y DV separados). |
| `core/utils.py` | `is_valid_email` | `ACTIVE` | Validación canónica de formato de correo RFC 5322. |
| `tools/populate_movements.py` | Script de reconciliación inicial | `COMPATIBILITY` | Utilizado para inicializar `inventory_movements` desde registros históricos. |
| `tools/reconcile_inventory.py` | Auditoría de paridad de stock | `ACTIVE` | Script de control periódico que asegura que el stock legacy no diverja del relacional. |
| `db.py` | `DEFAULT_DATA` | `COMPATIBILITY` | Diccionario maestro de inicialización de catálogos y fallback demo si la BD está vacía. |

---

## 3. Plan de Saneamiento y Recomendaciones

1. **Mantener Capa de Compatibilidad:**
   - La separación de `repositories/legacy_repo.py` aísla las funciones legacy, impidiendo que contaminen los repositorios de dominio puros (`sales_repo`, `inventory_repo`, `purchases_repo`).
2. **Monitoreo de Telemetría (Fase 6):**
   - En la Fase 6 se incorporará logging de advertencia estructurado (`logging.warning("DEPRECATED: ...")`) en `get_page_data` para registrar las plantillas HTML que aún requieran claves demo o desuso.
3. **Cero Impacto Funcional:**
   - Ninguna función clasificada como `COMPATIBILITY` ha sido eliminada en esta fase, preservando el 100% de la funcionalidad del ERP.
