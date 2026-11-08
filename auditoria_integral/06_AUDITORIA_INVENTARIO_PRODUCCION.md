# 06. AUDITORÍA DE INVENTARIO Y PRODUCCIÓN — FIFO, PPP Y REGLAS DE BODEGA

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Módulos Evaluados:** Inventario, Lotes, Kardex, Costeo PPP, Producción, Recetas (BOM) y Órdenes de Trabajo (OT).

---

## 1. REGLA ARQUITECTÓNICA DE INVENTARIO: RESERVA VS ASIGNACIÓN

### 1.1 Invariante de Stock
El motor de inventario (tanto en V1 como en V2) respeta la ecuación fundamental de bodega:
$$\text{Stock Disponible} = \text{Stock Físico} - \text{Stock Reservado}$$
**Regla de Negocio Protegida (`PAR-INV-02`):**
- La confirmación o paso a estado *Pendiente* de una venta genera una **reserva global de stock**, impidiendo sobreventas.
- **Autonomía Operativa de Bodega:** La reserva global **NO asigna lotes físicos específicos a un pedido de forma automática**. Es el operador en bodega quien decide qué pedido preparar primero y de qué ubicación/lote tomar físicamente la mercancía al momento del picking/despacho.
- Si dos ventas compiten por stock, ninguna se bloquea con lotes "secuestrados" artificialmente hasta que se ejecuta el despacho físico.

### 1.2 Consumo FIFO por Capas de Lotes (`PAR-INV-05`)
Al materializarse el despacho de venta o el consumo en una orden de trabajo:
- El sistema consulta los lotes disponibles ordenados estrictamente por:
  ```sql
  ORDER BY entry_date ASC, id ASC
  ```
- Se consumen las cantidades capa por capa (FIFO determinista). Si un lote no cubre el total, se agota y se continúa automáticamente con el siguiente lote más antiguo.

### 1.3 Costeo Contable PPP (Precio Promedio Ponderado - `PAR-INV-06`)
- El costo unitario contable del inventario se gestiona de forma desacoplada de los lotes físicos:
  $$\text{Nuevo PPP} = \frac{(\text{Stock Actual} \times \text{PPP Actual}) + (\text{Cantidad Recibida} \times \text{Costo Unitario Recepción})}{\text{Stock Actual} + \text{Cantidad Recibida}}$$
- Las salidas por venta o merma disminuyen el stock valorizado al PPP vigente en ese instante, sin alterar el PPP promedio ponderado unitario.

---

## 2. AUDITORÍA DEL MÓDULO DE PRODUCCIÓN (Fase 7)

### 2.1 Definición de Recetas (Bill of Materials - BOM)
- Una receta define los insumos necesarios para producir una unidad o lote de Producto Terminado (PT).
- El sistema valida que los componentes existan en el mismo tenant y que no existan dependencias circulares (un producto que sea insumo de sí mismo).

### 2.2 Ejecución de Órdenes de Trabajo (OT)
- **Consumo de Insumos:** Las materias primas se descuentan del inventario mediante el algoritmo FIFO, asociando los lotes exactos consumidos en la tabla `production_material_consumptions`.
- **Genealogía de Lotes:** Se guarda la trazabilidad completa que vincula los números de lote de las materias primas utilizadas con el nuevo lote generado del producto final (`production_lot_outputs`).
- **Costeo de Producto Terminado:** El costo del PT resultante es la sumatoria exacta del costo de las materias primas consumidas según su PPP/costo real de lote en el momento de la ejecución.

### 2.3 Idempotencia en el Cierre de OTs (`PAR-PRD-02`)
- En el endpoint de finalización de OT (`POST /api/v1/production/orders/{id}/complete`), el servicio verifica el estado previo bajo bloqueo transaccional (`FOR UPDATE`).
- Si la orden ya se encuentra en estado `COMPLETADA`, la operación no repite el consumo ni duplica el ingreso del producto terminado a bodega, devolviendo el resultado existente de forma segura.

---

## 3. HALLAZGOS Y RECOMENDACIONES EN INVENTARIO Y PRODUCCIÓN

| ID Hallazgo | Módulo | Descripción | Severidad | Recomendación |
|---|---|---|:---:|---|
| **INV-01** | Inventario | En V1 la interfaz de usuario no alerta visualmente cuando un lote está próximo a vencer (fecha de caducidad en menos de 30 días). | **P2** | Agregar un indicador visual (badge amarillo/rojo) en la tabla de existencias de lotes según fecha de expiración. |
| **INV-02** | Producción | No existe registro de mermas o desperdicios parciales durante el proceso de fabricación (scraping rate). | **P2** | En la Fase de ampliación funcional, agregar campo `waste_quantity` en el cierre de la orden de producción. |
| **INV-03** | Bodegas | V1 sólo maneja una bodega física central. V2 ya soporta múltiples almacenes pero no cuenta con traslados entre bodegas (inter-warehouse transfers). | **P2** | Diseñar para V2 el flujo de `stock_transfers` entre almacenes del mismo tenant con documento de despacho y recepción interna. |
