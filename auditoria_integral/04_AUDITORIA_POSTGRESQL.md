# 04. AUDITORÍA POSTGRESQL — ESQUEMAS, ÍNDICES Y SEGURIDAD RLS

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Motores Auditados:**
1. Base de datos `erp_multitenant_v2` (PostgreSQL 16 en contenedor port 5439)
2. Base de datos `facturacion` (PostgreSQL Local port 5432 - Legacy V1)

---

## 1. EVALUACIÓN DEL MODELO RELACIONAL V2

### 1.1 Políticas Row Level Security (RLS)
El modelo V2 utiliza una política sistemática de seguridad a nivel de fila:
1. **Columna troncal:** Toda tabla de negocio posee `tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT`.
2. **Activación estricta de RLS:**
   ```sql
   ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY;
   ALTER TABLE <tabla> FORCE ROW LEVEL SECURITY;
   ```
   *Nota crítica:* `FORCE ROW LEVEL SECURITY` es vital porque obliga a que incluso los usuarios propietarios de la tabla cumplan las políticas, impidiendo bypass accidental por permisos de conexión de la aplicación.
3. **Definición de Política Canónica:**
   ```sql
   CREATE POLICY <tabla>_tenant_isolation_policy ON <tabla>
       AS RESTRICTIVE
       USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::BIGINT)
       WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::BIGINT);
   ```

### 1.2 Integridad Referencial y Restricciones UNIQUE
- En V2, las restricciones de unicidad no son globales, sino compuestas por tenant:
  - `UNIQUE (tenant_id, sku)` en `products`.
  - `UNIQUE (tenant_id, rut)` en `customers` y `suppliers`.
  - `UNIQUE (tenant_id, order_number)` en `sales_orders` y `purchase_orders`.
  - `UNIQUE (tenant_id, account_number)` en `bank_accounts`.
- Esto permite que múltiples empresas utilicen sus propios códigos internos o atiendan a los mismos clientes sin colisiones de clave única en la base de datos compartida.

---

## 2. AUDITORÍA DE ÍNDICES Y RENDIMIENTO DE CONSULTAS

### 2.1 Cobertura de Índices en Clave Foránea y Filtros RLS
- Debido a que toda consulta evaluada por PostgreSQL RLS agrega la condición implícita `tenant_id = ...`, el primer campo en la mayoría de los índices compuestos debe ser `tenant_id`.
- **Estado en V2:**
  - 🟢 Las migraciones `000001` a `000008` definen índices compuestos como `CREATE INDEX idx_<tabla>_tenant ON <tabla>(tenant_id, created_at DESC)`.
  - 🟢 En `lot_stock`, el índice `(tenant_id, warehouse_id, product_id, available_qty)` soporta de forma instantánea la búsqueda de saldo por almacén.
  - 🟢 En `bank_transactions`, el índice `(tenant_id, bank_account_id, transaction_date)` optimiza la reconstrucción de saldos.

### 2.2 Tipos Monetarios y Redondeos
- En el esquema V2 se utiliza uniformemente `NUMERIC(14, 4)` o `NUMERIC(18, 4)` para montos monetarios, costos unitarios y existencias fraccionables (litros, kilos, etc.).
- Se descarta totalmente el uso de `FLOAT` o `REAL` en datos contables o balances, eliminando inconsistencias por redondeo binario IEEE 754.

---

## 3. AUDITORÍA COMPARATIVA: BASE V1 (FACTURACION)

| Aspecto | Base V2 (`erp_multitenant_v2`) | Base V1 (`facturacion`) |
|---|---|---|
| **Modelo de Tenancy** | Multitenant Nativo (Shared Database, Shared Schema con RLS) | Single-Tenant (No posee `tenant_id`) |
| **Protección RLS** | 100% activa con `FORCE ROW LEVEL SECURITY` | Desactivada |
| **Precisión Decimal** | `NUMERIC(14,4)` uniforme | Mixto (`NUMERIC(14,2)` y `DOUBLE PRECISION` en tablas iniciales) |
| **Control de Migraciones** | `golang-migrate` con archivos `.up.sql` y `.down.sql` versionados | Tabla `schema_migrations` personalizada (hasta versión 27) |
| **Integridad de Lotes** | Capas atómicas vinculadas a recepción y despacho | Tabla `lot_stock` con ajuste manual y movimientos |

---

## 4. HALLAZGOS Y RECOMENDACIONES DE BASE DE DATOS

| ID Hallazgo | Tabla / Objeto | Descripción | Severidad | Recomendación |
|---|---|---|:---:|---|
| **PG-DB-01** | `tenant_memberships` | Falta índice parcial en usuarios activos para login ultra-rápido. | **P3** | Crear `CREATE INDEX idx_memberships_active ON tenant_memberships(user_id, tenant_id) WHERE is_active = TRUE;`. |
| **PG-DB-02** | `bank_transactions` | Ausencia de particionamiento si se proyectan millones de movimientos. | **P2** | Para despliegues >1000 tenants, evaluar particionamiento declarativo por rango de fecha anual o por hash de `tenant_id`. |
| **PG-DB-03** | Rutinas de Mantenimiento | No se evidencian tareas de `VACUUM ANALYZE` programadas explícitamente para tablas con alto churn como `stock_commitments`. | **P2** | Ajustar los parámetros de autovacuum en PostgreSQL (`autovacuum_vacuum_scale_factor = 0.05` para tablas transaccionales de inventario). |
