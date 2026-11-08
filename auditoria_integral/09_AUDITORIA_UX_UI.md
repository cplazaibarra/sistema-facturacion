# 09. AUDITORÍA DE EXPERIENCIA DE USUARIO (UX/UI) — OPERABILIDAD Y DISEÑO

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Entornos Evaluados:** Interfaz Web ERP V1 (Jinja2 / Bootstrap / CSS personalizado) y Especificación de Contratos V2.  
**Perfiles de Usuario Analizados:** Administrador General, Encargado de Bodega, Vendedor, Analista de Compras y Responsable de Finanzas.

---

## 1. EVALUACIÓN DE NAVEGACIÓN Y MENÚS EN V1

### 1.1 Organización Modular
- La reciente reorganización unificó **Gastos Operacionales** y **Cuentas por Pagar** bajo el módulo central de **FINANZAS**, eliminando enlaces duplicados confusos que existían en Compras y Administración.
- La barra de navegación lateral es colapsable y cuenta con indicadores de contexto y búsqueda rápida (`navigation_search.js`).

### 1.2 Flujos Operativos y Fricciones Detectadas
1. **Encargado de Bodega (Recepción y Despacho):**
   - El módulo para operario (`operario_scanner.js`) permite la lectura de códigos de barra para picking y recepción rápida, lo cual es altamente eficiente para trabajo en bodega física.
   - *Fricción:* Cuando se realiza una recepción parcial, el operario debe salir de la pantalla de escaneo e ir al listado maestro para comprobar cuántas unidades restan por recibir de la OC.
2. **Vendedor (Cotizaciones y Ventas):**
   - La conversión de Cotización a Venta es de 1 solo clic, agilizando el cierre comercial.
   - *Fricción:* En la creación de cotizaciones con más de 10 productos, el scroll del formulario se alarga excesivamente sin un resumen flotante del subtotal e IVA.
3. **Responsable Financiero (Conciliación y Gastos):**
   - El modal de Gastos Operacionales fue optimizado: al seleccionar "Una vez", se ocultan automáticamente los selectores de reglas mensuales y días de recurrencia, evitando confusión.
   - El tratamiento de IVA (IVA incluido por defecto vs Exento) está visible y directo al lado del monto.

---

## 2. AUDITORÍA DE TABLAS, FILTROS Y PAGINACIÓN

- **Tablas de Datos:** Poseen tipografía clara (`Outfit`), contrastes adecuados y badges semánticos (verde para pagado/completado, amarillo para pendiente, rojo para vencido/cancelado).
- **Filtros:** Los filtros por rango de fecha, estado y proveedor/cliente están presentes en casi todas las vistas.
- **Paginación:** En vistas críticas de ventas e inventario la paginación es rápida, pero en reportes históricos extensos se detecta cierta lentitud al renderizar tablas HTML con más de 500 filas simultáneas sin paginación virtual o server-side en V1.

---

## 3. HALLAZGOS Y RECOMENDACIONES DE EXPERIENCIA DE USUARIO

| ID Hallazgo | Pantalla / Módulo | Descripción | Severidad | Recomendación UX |
|---|---|---|:---:|---|
| **UX-01** | Plataforma V2 | **V2 no cuenta con frontend gráfico**. La migración actual es 100% API REST. | **P1** | Construir un frontend web moderno (React/Vue/Tailwind) o implementar un adaptador web que permita reutilizar las vistas HTML consumiendo el API V2. |
| **UX-02** | Reportes Financieros | Ciertos reportes no mantienen los filtros seleccionados en la URL tras recargar la página (falta persistencia en query params). | **P2** | Sincronizar todos los estados de filtros y paginación en los search params de la URL para permitir compartir enlaces directos y recordar búsquedas. |
| **UX-03** | Ventas / Cotizaciones | Falta confirmación previa antes de salir de una cotización con cambios no guardados. | **P2** | Agregar hook `beforeunload` en JavaScript si el formulario tiene campos modificados para evitar pérdidas accidentales de datos. |
| **UX-04** | Alertas Operativas | Los avisos de confirmación (`flash messages`) a veces se superponen brevemente con modales abiertos. | **P3** | Ajustar el `z-index` de los toasts de notificación (`z-index: 3000`) para que queden siempre visibles por encima de cualquier modal. |
