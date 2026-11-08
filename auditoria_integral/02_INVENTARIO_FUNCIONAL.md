# 02. INVENTARIO FUNCIONAL — AUDITORÍA COMPARATIVA V1 vs V2

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Criterio de Evaluación:** Comparación entre contratos de negocio, implementación real en ERP V1 (Flask) y estado de migración en ERP V2 (Go).

---

## 1. ESTADO DE DOMINIOS Y MÓDULOS

| Módulo / Dominio | ERP V1 (Flask Single-Tenant) | ERP V2 (Go Multitenant) | Estado de Paridad | Observaciones Técnicas |
|---|:---:|:---:|:---:|---|
| **Autenticación y Sesiones** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | V1 usa sesiones Flask + Cookies; V2 usa JWT Bearer + Argon2id + contexto de Tenant en request. |
| **Tenancy y Membresías** | NO APLICA | IMPLEMENTADO | **IMPLEMENTADO (V2)** | V1 es single-tenant; V2 tiene CRUD de Tenants, membresías y roles asignables. |
| **Clientes (Customers)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | CRUD completo, validación de RUT chileno, soft delete (`is_active`). |
| **Proveedores (Suppliers)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Términos de pago estandarizados (`CASH`, `NET_30`, `NET_60`), RUT, aislamiento tenant. |
| **Productos (Catalog)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | SKU único por tenant, categoría, precio venta, costo base, flag `requires_lot`. |
| **Bodegas (Warehouses)** | PARCIAL (1 Bodega global) | IMPLEMENTADO | **IMPLEMENTADO (V2)** | V2 soporta múltiples bodegas tenant-scoped con control de stock segregado. |
| **Inventario Físico / Lotes** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Trazabilidad por lotes (`lot_number`, vencimiento, recepción), balance estricto. |
| **Motor de Reserva de Stock** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Stock Físico vs Reservado vs Disponible. Regla: la reserva global no asigna físicamente. |
| **Asignación FIFO** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Consumo físico por capas de lote (`entry_date ASC, id ASC`). |
| **Costeo PPP (Ponderado)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Valoración contable promedio ponderado independiente de capas de lote. |
| **Ajustes de Inventario** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Solicitudes de ajuste con aprobación de dos pasos (merma, conteo físico). |
| **Órdenes de Compra (OC)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Flujo: Borrador -> Aprobada -> Recibida (Parcial/Total). OC no impacta stock. |
| **Recepciones de Compra** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Genera movimientos de inventario, capas de lotes y recalcula PPP. |
| **Cuentas por Pagar (CxP)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Factura crea obligación; pagos reducen saldo. Validaciones de no-sobrepago. |
| **Cotizaciones (Quotations)**| IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Vida útil, estado ganado/perdido. No afecta stock ni reserva. |
| **Ventas (Sales Orders)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Transición a Pendiente genera reserva; Despacho consume stock físico por FIFO. |
| **Despachos (Dispatches)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Asignación y egreso físico definitivo con número de guía/remisión. |
| **Cuentas por Cobrar (CxC)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Factura/boleta de venta crea obligación; cobros aplican saldo. |
| **Recetas (BOM)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Lista de materiales con factor de rendimiento y componentes requeridos. |
| **Órdenes de Trabajo (OT)** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Consumo exacto de insumos, costeo FIFO de materias primas y alta de PT con lote. Idempotente. |
| **Cuentas Bancarias** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Registro de cuentas, moneda, saldo derivado de libro de transacciones (`bank_transactions`). |
| **Cartolas y Transacciones** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Importación con hash SHA-256 deduplicador, tipificación y auditoría. |
| **Conciliación Bancaria** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Vinculación neutral con cobros, pagos y transferencias. Cero impacto económico duplicado. |
| **Transferencias Internas** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Transacción ACID con par débito/crédito, neto cero e idempotencia. |
| **Deudas Financieras** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Modelo `Deuda != Cuota != Pago`. Amortización francesa/alemana y validación de saldo. |
| **Acciones de Cobranza** | IMPLEMENTADO | IMPLEMENTADO | **PARITY_GREEN** | Bitácora de gestiones de cobro sin alteración de balance contable de CxC. |
| **Gastos Operacionales** | IMPLEMENTADO | EN DISEÑO | **DESIGNED (Fase 9)** | V1 posee maestro recurrente + ocurrencias mensuales + IVA. V2 tiene diseño cerrado en `PLAN_FASE_9.md`. |
| **Flujo de Caja Consolidado** | IMPLEMENTADO | EN DISEÑO | **DESIGNED (Fase 9)** | V1 cuenta con proyecciones y realizados. V2 tiene diseño cerrado para cálculo en SQL. |
| **Reportería Unificada / Export** | IMPLEMENTADO | EN DISEÑO | **DESIGNED** | En V1 opera mediante Pandas/openpyxl con regla Detail=KPI=Export. En V2 pendiente tras Fase 9. |
| **Interfaz de Usuario Web** | IMPLEMENTADO (V1) | NO IMPLEMENTADO | **PENDIENTE (V2)** | V1 tiene interfaz web Jinja2 completa. V2 es API REST (requiere SPA o port de vistas). |

---

## 2. DETALLE DE CAPACIDADES FALTANTES Y BRECHAS

1. **Gastos Operacionales (V2)**: Falta transcribir el modelo de maestros de gastos, ocurrencias periódicas y tratamiento tributario (IVA incluido / Exento) al esquema multitenant con RLS de Go.
2. **Flujo de Caja Consolidado (V2)**: Falta implementar el servicio consolidado que combine `bank_transactions`, `accounts_payable`, `accounts_receivable`, `debt_payments` y gastos operacionales sin doble contabilización.
3. **Paginación Nativa en Base de Datos**: V2 implementa paginación `LIMIT/OFFSET` con totalizador `COUNT(*) OVER()` en todos sus endpoints. V1 posee algunos reportes que traen datos completos a memoria Python antes de paginar.
4. **Capa Visual para V2**: El backend V2 no expone templates HTML ni bundle de frontend (es headless). Se requiere definir si se utilizará un frontend React/Vue moderno o si se adaptará la interfaz Jinja existente como cliente HTTP del API.
