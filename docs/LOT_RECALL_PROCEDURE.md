# Procedimiento de Retiro de Producto / Recall de Lotes (Fase 5B)

**Fecha:** 15 de Septiembre de 2026  
**Sistema:** ERP Facturación & Gestión de Negocio  

---

## 1. Propósito

Establecer el procedimiento automatizado para responder ante alertas de inocuidad o calidad, identificando instantáneamente el impacto bidireccional (hacia adelante y hacia atrás) de cualquier lote contaminado o defectuoso.

---

## 2. Alcance del Análisis de Impacto (`get_lot_recall_impact`)

Dado un `lot_id` sospechoso (por ejemplo, materia prima `MP-001`), el motor de trazabilidad recorre automáticamente:

1. **Órdenes de Trabajo Afectadas:** Todas las OTs que consumieron directa o indirectamente dicho lote en cualquier nivel de transformación.
2. **Lotes Derivados Producidos:** Lotes de subproductos y productos terminados que incorporaron el lote sospechoso.
3. **Ventas y Despachos Impactados:** Todas las ventas que recibieron productos terminados derivados.
4. **Clientes Afectados:** Nombre, correo y datos de contacto de los clientes que adquirieron las unidades.
5. **Inventario Remanente en Bodega:** Unidades que aún permanecen en bodega (sin vender) para su inmediato bloqueo/cuarentena.

---

## 3. Consulta de Recorrido Recursivo (PostgreSQL `WITH RECURSIVE`)

```sql
WITH RECURSIVE lot_tree AS (
    -- Caso Base: Lote investigado
    SELECT id as lot_id, product_id, lot_number, 0 as depth
    FROM lots
    WHERE id = :target_lot_id

    UNION ALL

    -- Caso Recursivo: Lotes producidos por OTs que consumieron el lote
    SELECT plo.output_lot_id, plo.output_product_id, l.lot_number, lt.depth + 1
    FROM lot_tree lt
    JOIN production_lot_consumptions plc ON plc.input_lot_id = lt.lot_id
    JOIN production_lot_outputs plo ON plo.production_order_id = plc.production_order_id
    JOIN lots l ON l.id = plo.output_lot_id
    WHERE lt.depth < 10 -- Previene ciclos
)
SELECT * FROM lot_tree;
```

---

## 4. Protocolo de Acción Operativo

1. **Ejecutar Consulta de Impacto:** Invocar `GET /api/lots/<id>/recall-impact` o el panel administrativo.
2. **Cuarentena Inmediata:** Actualizar el estado de los lotes identificados a `'QUARANTINE'` o `'RECALLED'` para impedir nuevas ventas automáticas.
3. **Contactar Clientes:** Exportar el listado de clientes y ventas afectadas para notificar la alerta sanitaria.
4. **Auditoría:** Conservar el registro inmutable del evento de recall.
