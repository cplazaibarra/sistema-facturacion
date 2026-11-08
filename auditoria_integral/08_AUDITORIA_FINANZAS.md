# 08. AUDITORÍA FINANCIERA — TESORERÍA, GASTOS, BANCOS Y FLUJO DE CAJA

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Módulos Evaluados:** Cuentas Bancarias, Cartolas, Conciliación, Deudas Financieras, Gastos Operacionales y Flujo de Caja.

---

## 1. PRINCIPIOS CONTABLES Y NEUTRALIDAD FINANCIERA

### 1.1 Saldo Bancario como Función Derivada (`PAR-BNK-01`)
- **Regla Fundamental:** En el modelo de tesorería, el saldo de una cuenta bancaria **NUNCA es un campo escalar directamente editable**.
- El saldo se calcula en tiempo real como la sumatoria de las transacciones efectivas registradas en `bank_transactions`:
  $$\text{Saldo Cuenta} = \sum \text{Monto Transacciones Bancarias}$$
- Esto evita discordancias contables entre el saldo reportado y la cartola bancaria oficial.

### 1.2 Neutralidad de la Conciliación Bancaria (`PAR-BNK-02`)
- La conciliación bancaria es una operación de **cruce documental**, no un movimiento económico.
- Vincular una transacción de cartola con un pago de factura (CxP) o un cobro de cliente (CxC) cambia el estado de conciliación (`is_reconciled = TRUE`), pero **NO crea un nuevo movimiento de dinero ni duplica el saldo en la cuenta**.
- La desconciliación revierte el vínculo de manera neutral e idempotente.

### 1.3 Transferencias Internas con Neto Cero (`PAR-BNK-03`)
- Al mover dinero entre dos cuentas de la misma empresa (`internal_transfers`), el sistema genera una única transacción atómica con dos registros en `bank_transactions`:
  - Débito: $-X$ en la cuenta de origen.
  - Crédito: $+X$ en la cuenta de destino.
- Efecto consolidado en el patrimonio: exactamente $0.00$.

### 1.4 Modelo de Deudas Financieras (`PAR-FIN-01`)
- Distinción canónica entre **Deuda Principal**, **Cuotas Programadas** y **Pagos Efectivos**:
  - `debts`: Registro del crédito bancario, monto original, tasa de interés y plazo.
  - `debt_installments`: Cronograma de amortización con desglose de capital, intereses y vencimiento.
  - `debt_payments`: Pagos reales aplicados a cada cuota, con validación de no-sobrepago.

---

## 2. GASTOS OPERACIONALES Y GASTOS RECURRENTES

### 2.1 Regla Arquitectónica Obligatoria
- **Ubicación Funcional:** Los Gastos Operacionales pertenecen y deben permanecer estrictamente dentro del módulo de **FINANZAS**, integrándose directamente con **Cuentas por Pagar (CxP)** y el **Flujo de Caja**.

### 2.2 Separación entre Regla Recurrente y Ocurrencias Materializadas
- **Regla Maestra:** Define la periodicidad (Mensual, Trimestral, Anual o "Una vez"), monto base, día de vencimiento, proveedor y condición de IVA (IVA incluido o Exento).
- **Materialización Periódica:** Cada mes se genera una ocurrencia específica en Cuentas por Pagar. Esta ocurrencia permite:
  - Ajustar el monto real según la factura del mes (ej. cuenta de luz o agua que varía).
  - Adjuntar el comprobante o factura en PDF.
  - Registrar pagos parciales o totales.
- **Prevención de Duplicación en Flujo de Caja:** El motor de proyección proyecta únicamente hacia el futuro desde la última ocurrencia materializada, garantizando que un período ya facturado no se cuente dos veces (como proyección y como deuda real).

---

## 3. AUDITORÍA DEL FLUJO DE CAJA (Plan Fase 9)

El diseño formal de la Fase 9 (`PLAN_FASE_9.md`) establece los criterios de consolidación:
1. **Movimientos Reales (Pasado/Presente):** Provenientes de `bank_transactions` efectivamente cobradas o pagadas.
2. **Compromisos Ciertos (Corto Plazo):**
   - Cuentas por Cobrar pendientes con fecha de vencimiento.
   - Cuentas por Pagar pendientes (proveedores y gastos operacionales materializados).
   - Cuotas de deudas bancarias próximas a vencer.
3. **Proyecciones Estimadas (Mediano Plazo):**
   - Gastos operacionales recurrentes activos para fechas futuras donde no existe ocurrencia física.
   - Ventas recurrentes estimadas (si existieran contratos periódicos).
4. **Agrupación y Paginación en SQL:** Todo el agrupamiento por día/semana/mes y los totales acumulados se calculan en base de datos mediante window functions (`SUM() OVER (...)`), eliminando la sobrecarga de memoria en el servidor web.

---

## 4. HALLAZGOS Y RECOMENDACIONES FINANCIERAS

| ID Hallazgo | Módulo | Descripción | Severidad | Recomendación |
|---|---|---|:---:|---|
| **FIN-01** | Finanzas V2 | **Fase 9 aún no implementada en Go**. Los gastos operacionales y el flujo de caja consolidado sólo existen en V1 y en el documento de diseño V2. | **P1** | Proceder con la implementación de la Fase 9 en Go siguiendo estrictamente las especificaciones de `PLAN_FASE_9.md`. |
| **FIN-02** | Tesorería V1 | En V1 la conciliación bancaria histórica permitía en casos aislados seleccionar un movimiento con monto levemente dispar sin advertir explícitamente la diferencia al usuario. | **P2** | Exigir en V2 que si el monto de la cartola difiere del monto del pago, se registre una cuenta de ajuste por diferencia de cambio/redondeo. |
| **FIN-03** | Monedas | El sistema opera fundamentalmente en Pesos Chilenos (CLP) sin soporte nativo de multi-divisa (USD, EUR, UF) con tipos de cambio diarios. | **P2** | Para clientes que importan insumos en USD, incorporar tabla de tipos de cambio oficiales y conversión automática a CLP. |
