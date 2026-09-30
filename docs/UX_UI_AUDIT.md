# AUDITORÍA GLOBAL DE UX/UI, USABILIDAD Y CONSISTENCIA VISUAL — ERP BODEGA MIEL

**Autor:** `ux_ui_design_agent` (Senior Product Designer / UX Architect)  
**Fecha:** 18 de Septiembre de 2026  
**Alcance:** 100% de las rutas, plantillas y componentes del sistema ERP (62 plantillas analizadas, 8 módulos principales + módulo móvil PWA).  
**Principio Rector:** **SIMPLICIDAD > DECORACIÓN**. El sistema debe ser intuitivo, rápido y predecible antes que cosmético.

---

## 1. Resumen Ejecutivo

El ERP "Sistema de Facturación / Bodega Miel" ha alcanzado una madurez funcional y técnica sobresaliente: alta resiliencia transaccional en PostgreSQL, $O(1)$ en consultas SQL para catálogos masivos y 259 pruebas automatizadas en verde.

Sin embargo, a nivel de **Experiencia de Usuario (UX) e Interfaz (UI)**, la aplicación exhibe los síntomas típicos de un software empresarial que creció orgánicamente mediante adición iterativa de características:
1. **Navegación Fractal y Sobrecarga del Sidebar:** Hay 6 secciones principales con hasta 7 sub-elementos cada una. Ciertos conceptos están duplicados o dispersos (ej. *Productos* vs *Inventario/Stock* vs *Kardex*; *Cuentas por Pagar* en Compras vs *Flujo de Caja* en Reportes).
2. **Proliferación de Modales y Formularios en Línea:** En `/productos`, `/proveedores` y `/clientes` coexisten formularios ocultos tipo acordeón ("Agregar Nuevo") con modales flotantes y pantallas de edición dedicadas (`/editar`), generando inconsistencia sobre cómo se crea o edita una entidad.
3. **Variabilidad en Componentes Visuales:** Existen botones primarios con múltiples tonalidades de azul (`#2563eb`, `#1E3A8A`, `#2b6cb0`, `#3182ce`), botones de éxito con diferentes bordes e iconos no estandarizados.
4. **Falta de Feedback y Estados Vacíos Guiados:** Varias pantallas cuando no tienen datos solo muestran una tabla vacía sin mensaje explicativo ni botón de acción rápida (empty states pobres).

---

## 2. Inventario Completo de Pantallas y Score UX

Cada pantalla fue evaluada asignando un puntaje de **1 a 10** en 7 dimensiones fundamentales:
- **CLA:** Claridad de propósito
- **NAV:** Navegabilidad y retorno
- **CON:** Consistencia visual y de componentes
- **EFI:** Eficiencia operacional (clicks y atajos)
- **ERR:** Prevención de errores humanos
- **RES:** Comportamiento responsive
- **ACC:** Accesibilidad y contraste

| Módulo | Ruta | Pantalla | Objetivo Operacional | CLA | NAV | CON | EFI | ERR | RES | ACC | Promedio | Prioridad |
|---|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Dashboard** | `/` | Dashboard | Visión general de ventas, alertas de stock y KPIs | 8 | 8 | 8 | 7 | 8 | 7 | 8 | **7.7** | UX-P2 |
| **Bodega** | `/inventario` | Stock / Existencias | Control de existencias físicas por producto | 7 | 7 | 7 | 7 | 8 | 6 | 7 | **7.0** | UX-P1 |
| **Bodega** | `/ingreso-mercaderia`| Ingreso Mercadería | Recepción administrativa y asignación de lotes | 7 | 6 | 6 | 6 | 7 | 6 | 7 | **6.4** | UX-P1 |
| **Bodega** | `/trazabilidad` | Trazabilidad Lotes | Genealogía backward/forward de lotes | 8 | 8 | 7 | 7 | 9 | 7 | 7 | **7.6** | UX-P2 |
| **Productos**| `/productos` | Catálogo Maestro | Consulta, alta, baja, export/import Excel | 8 | 7 | 7 | 8 | 8 | 7 | 8 | **7.6** | UX-P1 |
| **Productos**| `/productos/importar/preview` | Preview Excel | Previsualización de diffs antes de persistir | 9 | 9 | 9 | 9 | 9 | 8 | 8 | **8.7** | UX-P3 |
| **Productos**| `/kardex` | Kardex Valorizado | Movimientos y costeo PPP ponderado | 8 | 8 | 8 | 7 | 9 | 6 | 7 | **7.6** | UX-P2 |
| **Producción**| `/produccion` | Fabricación (OTs) | Lista de Órdenes de Trabajo y estados | 7 | 7 | 7 | 7 | 8 | 7 | 7 | **7.1** | UX-P1 |
| **Producción**| `/produccion/nueva` | Nueva OT | Creación y cálculo BOM de orden fabril | 7 | 7 | 6 | 6 | 8 | 6 | 7 | **6.7** | UX-P1 |
| **Producción**| `/produccion/recetas`| Recetas / BOM | Formulación técnica y consumo de insumos | 8 | 8 | 8 | 7 | 8 | 7 | 8 | **7.7** | UX-P2 |
| **Producción**| `/produccion/calendario`| Programación | Gantt/Calendario de planificación fabril | 8 | 7 | 8 | 7 | 8 | 6 | 7 | **7.3** | UX-P2 |
| **Ventas** | `/ventas` | Gestión de Ventas | Flujo comercial, facturación y cobro | 8 | 8 | 8 | 8 | 8 | 7 | 8 | **7.9** | UX-P1 |
| **Ventas** | `/ventas/cotizaciones`| Cotizaciones | Estimación de precios, márgenes y conversión | 7 | 7 | 7 | 7 | 7 | 7 | 7 | **7.0** | UX-P1 |
| **Ventas** | `/ventas/cotizacion/nueva`| Nueva Cotización | Armado de presupuesto línea por línea | 7 | 6 | 6 | 6 | 7 | 6 | 7 | **6.4** | UX-P0 |
| **Ventas** | `/ventas/clientes` | Clientes | Maestro de clientes comerciales | 7 | 7 | 7 | 7 | 8 | 7 | 7 | **7.1** | UX-P2 |
| **Compras** | `/compras/oc` | Órdenes de Compra | Ciclo de compras a proveedores | 8 | 8 | 8 | 8 | 8 | 7 | 8 | **7.9** | UX-P1 |
| **Compras** | `/compras/oc/nueva` | Nueva OC | Creación y detalle de ítems de compra | 7 | 7 | 7 | 7 | 8 | 7 | 7 | **7.1** | UX-P1 |
| **Compras** | `/compras/cuentas-por-pagar`| CxP Proveedores | Facturas y vencimientos pendientes | 8 | 8 | 7 | 7 | 8 | 6 | 7 | **7.3** | UX-P1 |
| **Compras** | `/proveedores` | Proveedores | Directorio y datos de contacto | 7 | 7 | 7 | 7 | 8 | 7 | 7 | **7.1** | UX-P2 |
| **Reportes** | `/reporteria/flujo-caja`| Flujo de Caja | Entradas, salidas y liquidez financiera | 8 | 8 | 8 | 7 | 9 | 7 | 7 | **7.7** | UX-P2 |
| **Reportes** | `/reporteria/inventario-lotes`| Lotes de Bodega | Existencias por lote físico y vencimientos | 8 | 7 | 8 | 7 | 8 | 7 | 7 | **7.1** | UX-P2 |
| **Admin** | `/usuarios` | Usuarios y Roles | Cuentas de usuario y asignación RBAC | 7 | 7 | 7 | 7 | 8 | 7 | 7 | **7.1** | UX-P2 |
| **Operario** | `/operario/` | PWA Móvil Bodega | App simplificada para recepción y OT | 9 | 9 | 9 | 9 | 9 | 9 | 9 | **9.0** | UX-P3 |

---

## 3. Mapa de Navegación y Arquitectura de Información

### Estructura Actual
```text
Sidebar:
├── Dashboard (/)
├── Ventas
│   ├── Ventas (/ventas)
│   ├── Cotizaciones (/ventas/cotizaciones)
│   ├── Listas de Precios (/administracion/listas-precios)  [Ubicada en Ventas pero bajo prefijo /administracion]
│   └── Clientes (/ventas/clientes)
├── Bodega
│   ├── Stock / Inventario (/inventario)
│   ├── Ingreso Mercadería (/ingreso-mercaderia)
│   └── Trazabilidad de Lotes (/trazabilidad)
├── Productos
│   ├── Productos (/productos)
│   ├── Kardex Valorizado / PPP (/kardex)
│   ├── Fabricación (/produccion)
│   └── Programación OT (/produccion/calendario)
├── Compra
│   ├── Órdenes de Compra (/compras/oc)
│   ├── Cuentas por Pagar (/compras/cuentas-por-pagar)
│   ├── Productos Comprados (/compras/productos-comprados)
│   └── Proveedores (/proveedores)
├── Administración
│   ├── Cuentas Bancarias (/administracion/cuentas-bancarias)
│   ├── Usuarios (/usuarios)
│   └── Roles y Permisos (/roles)
└── Reportería (7 submenús)
```

### Problemas Detectados en Navegación
1. **Confusión entre "Bodega" y "Productos":**
   - El usuario común no distingue fácilmente por qué *Stock / Inventario* está en *Bodega*, mientras que *Productos* y *Kardex* están en *Productos*.
2. **Ubicación de Fabricación / OT:**
   - *Fabricación* está alojada como un submenú de *Productos*. Conceptualmente, en una fábrica de alimentos, la Producción es un área de nivel 1 con sus propios flujos operacionales.
3. **Falta de Migas de Pan (Breadcrumbs):**
   - Al entrar a editar un registro (ej. `/productos/14/editar` o `/compras/oc/12/editar`), no hay un rastro claro para volver a la lista anterior sin depender del botón "Atrás" del navegador.

---

## 4. Principales Flujos Operacionales (Journeys)

### Journey 1: Compra e Ingreso de Mercadería
- **Flujo:** Proveedores → Nueva OC → Aprobar OC → Ingreso Mercadería → Kardex.
- **Punto de Fricción UX:** Al aprobar una OC en `/compras/oc`, el usuario no recibe un botón directo "Recibir mercadería de esta OC", sino que debe ir manualmente a *Bodega → Ingreso Mercadería*, buscar el selector de OCs y volver a cargar los ítems.
- **Mejora Propuesta:** Botón de acción directa `[ 📥 Recepcionar en Bodega ]` desde la fila de la OC aprobada.

### Journey 2: Cotización a Facturación
- **Flujo:** Cliente → Nueva Cotización → Negociación → Convertir a Venta → Registrar Cobro.
- **Punto de Fricción UX:** El formulario `/ventas/cotizacion/nueva` es largo y tabular. Si falta crear un cliente, el modal no siempre refresca el selector principal sin perder los ítems cargados en memoria.
- **Mejora Propuesta:** Autosave local (Draft) y selector con búsqueda asíncrona ágil.

---

## 5. Clasificación de Hallazgos UX (P0, P1, P2, P3)

### UX-P0 (Bloqueos o Fricción Severa)
- **UX-P0.1 — Pérdida de Datos en Formularios Largos al Cancelar o Navegar:**
  - En `/ventas/cotizacion/nueva` y `/produccion/nueva`, si el operador añade 10 filas de insumos y hace clic accidentalmente fuera o en un link del sidebar, no hay advertencia de confirmación (`beforeunload`), perdiéndose el trabajo.

### UX-P1 (Confusión Frecuente / Riesgo de Error Humano)
- **UX-P1.1 — Coexistencia de 3 Modos de Creación/Edición de Productos:**
  - En `/productos` hay un botón que despliega un formulario oculto en la parte superior; en `/productos/<id>/editar` hay una página completa; y en ciertos flujos hay modales. Esto confunde al usuario sobre cuál es el formulario oficial.
- **UX-P1.2 — Confirmación de Acciones Destructivas:**
  - Ciertas eliminaciones usan el `confirm()` nativo del navegador, que resulta invasivo y arcaico. Debe sustituirse por un modal limpio con mensaje explicativo de impacto.
- **UX-P1.3 — Falta de Acción Rápida para Recepcionar OC:**
  - Desconexión visual entre la aprobación de la orden de compra y su ingreso a bodega.

### UX-P2 (Reducción de Productividad)
- **UX-P2.1 — Falta de Breadcrumbs en Formularios Secundarios:**
  - En pantallas de edición (`editar_producto`, `editar_oc`, `editar_ot`), falta un encabezado con rastro de navegación.
- **UX-P2.2 — Variabilidad de Colores en Botones de Acción:**
  - Coexisten botones primarios con fondos `#2563eb`, `#1E3A8A` y `#2b6cb0`.
- **UX-P2.3 — Densidad Excesiva en Tablas con Desplazamiento Horizontal:**
  - Tablas con más de 18 columnas obligan a un scroll horizontal extenso en notebooks de 13"-15". Deben ocultarse columnas secundarias en vistas predeterminadas mediante selector de columnas.

### UX-P3 (Pulido Visual / Cosmético)
- **UX-P3.1 — Iconografía Heterogénea:**
  - Mezcla de emojis (`➕`, `🏭`, `📥`) con iconos FontAwesome (`<i class="fa-solid fa-file-excel"></i>`). Estandarizar hacia FontAwesome 6 sólido.
- **UX-P3.2 — Estilización de Badges de Estado:**
  - Unificar los badges de estados (`Activo`, `Inactivo`, `Emitida`, `Pagada`, `Recibida`) con paletas semánticas pastel normalizadas.

---

## 6. Design System Recomendado (Ligero y Nativo)

Sin introducir librerías externas ni frameworks SPA pesados, se define el siguiente estándar para consolidar en `static/css/style.css`:

### 6.1 Paleta Semántica
- **Primary (Acción Principal):** `#1E3A8A` (Azul corporativo oscuro) / Hover: `#1e40af`
- **Secondary (Acción Neutral):** `#f8fafc` (Borde `#cbd5e1`, Texto `#334155`)
- **Success (Confirmación / Aprobación / Exportación):** `#10b981` / Hover: `#059669`
- **Warning (Alertas / Modificaciones):** `#f59e0b` / Texto `#92400e`
- **Danger (Eliminación / Anulación):** `#ef4444` / Hover: `#dc2626`

### 6.2 Jerarquía de Botones
1. **Botón Primario:** Uno solo por vista visible (la acción más importante, ej. `[ + Nueva Cotización ]` o `[ Guardar Producto ]`).
2. **Botón Secundario:** Cancelar, Filtros, Volver.
3. **Botón de Peligro:** Eliminar, Anular (siempre con confirmación explícita).

### 6.3 Tipografía y Formatos Numéricos
- Tipografía base: `Inter, system-ui, -apple-system, sans-serif`
- **Moneda:** `$ 1.250.000` (pesos chilenos con punto separador de miles, sin decimales para CLP).
- **Fechas:** `DD/MM/AAAA` (estándar nacional consistente).

---

## 7. Quick Wins (Mejoras Inmediatas de Alto Impacto y Bajo Riesgo)
1. Estandarizar la iconografía en la barra superior de `/productos` (cambiar emojis por FontAwesome).
2. Agregar breadcrumbs en todas las pantallas de edición `/editar`.
3. Agregar confirmación con modal para eliminación de productos y órdenes.
4. Agregar enlace directo "Recibir en Bodega" en la tabla de órdenes de compra aprobadas.

---

## 8. Roadmap de Implementación UX/UI

- **FASE 0 — Design System y Estandarización de Componentes:**
  - Normalizar variables CSS de botones, inputs, badges y modales en `style.css`.
- **FASE 1 — Navegación y Breadcrumbs:**
  - Agregar barra de navegación contextual y breadcrumbs en vistas secundarias.
- **FASE 2 — Formularios Críticos y Prevención de Pérdida de Datos:**
  - Implementar feedback contra cierre accidental y unificar modo de edición en `/productos` y `/compras`.
- **FASE 3 — Tablas de Datos y Filtros:**
  - Optimizar visualización responsive de tablas densas en notebooks.
- **FASE 4 — Estados Vacíos y Accesibilidad:**
  - Enriquecer tablas vacías con llamadas a la acción guiadas y verificar contraste WCAG AA.
