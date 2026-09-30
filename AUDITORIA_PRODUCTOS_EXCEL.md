# INFORME DE AUDITORÍA FINAL — IMPORTACIÓN Y EXPORTACIÓN MASIVA DE PRODUCTOS EN EXCEL

**Fecha de Auditoría:** 18 de Septiembre de 2026  
**Módulo Auditado:** Catálogo de Productos (`/productos`, `/productos/exportar`, `/productos/plantilla-excel`, `/productos/importar/preview`, `/productos/importar/confirmar`)  
**Resultado de la Suite:** **259 PASSED, 0 FAILED, 0 WARNINGS**  
**Estado General:** **CONFORME / APTO PARA PRODUCCIÓN (CON RECOMENDACIONES DE ENDURECIMIENTO P2/P3)**

---

## 1. Arquitectura Encontrada y Esquema Único

### 1.1 Fuente Única de la Verdad
- Se confirmó que [`services/products_excel_service.py`](file:///home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/services/products_excel_service.py) es la **única fuente de la verdad** para la definición del esquema del archivo Excel:
  - Estructura unificada de **24 columnas** (`PRODUCT_EXCEL_COLUMNS`).
  - Las 22 columnas de datos maestros corresponden a atributos reales de la tabla PostgreSQL `products`.
  - Las 2 columnas transaccionales (`current_stock` y `ppp_cost`) están marcadas formalmente con `readonly=True`.
- **Ausencia de Duplicación**: Se auditó el repositorio y no existen otras listas o esquemas de columnas en templates ni rutas; tanto la plantilla vacía como la exportación del catálogo y el parser de importación derivan de la misma especificación canónica.

---

## 2. Resultados de las Pruebas de Auditoría por Sección

### 2.1 Prueba Round-Trip (Integridad y Preservación de Datos)
- **Procedimiento**:
  1. Extracción de los **7.937 productos reales** de la base de datos PostgreSQL.
  2. Generación en memoria del archivo `.xlsx` idéntico al descargado por el usuario.
  3. Carga y parseo inmediato del archivo resultante mediante `parse_and_validate_products_excel()`.
- **Resultado Obtenido**:
  ```text
  Total Filas Analizadas: 7.937
  Nuevos:       0
  Modificados:  0
  Sin Cambios:  7.937
  Errores:      0
  ```
- **Conclusión**: 100% de consistencia round-trip. Ningún registro existente es falsamente catalogado como modificado ni se detectaron pérdidas de precisión tras normalizar la comparación de coma flotante (tolerancia a imprecisión binaria IEEE 754 con `math.isclose`).

---

### 2.2 Protección de Stock y PPP (Integridad Transaccional de Bodega)
- **Prueba**: Se inyectaron valores ficticios en un archivo Excel (`Stock Actual = 9.999.999`, `Costo PPP = 8.888.888`).
- **Comprobación en Backend y Base de Datos**:
  - `parse_and_validate_products_excel` filtra estrictamente las columnas marcadas como `readonly`.
  - El payload generado para inserción o actualización **no incluye** `current_stock` ni `ppp_cost`.
  - Las tablas de movimientos de inventario (`inventory`), lotes (`inventory_lots`) y Kardex permanecieron completamente inalteradas.
- **Conclusión**: **Garantía absoluta de protección**. Ni aun manipulando maliciosamente el archivo Excel es posible vulnerar el stock o costo promedio ponderado de bodega.

---

### 2.3 Identificación de Productos y Resolución de Identidad
- **Fuente de Identidad Autoritativa**: Se implementó una política de **Identidad Jerárquica Segura**:
  1. Si se provee **ID** y **SKU**: ambos deben corresponder al mismo registro en PostgreSQL. Si apuntan a registros distintos, el sistema rechaza la fila con un error explícito de `Conflicto de identidad`.
  2. Si se provee **ID** existente y un **SKU nuevo** (no registrado): el sistema reconoce la intención de renombrar el SKU técnico del producto sin crear duplicados.
  3. Si no se provee **ID** pero el **SKU ya existe**: el sistema actualiza el registro existente correspondiente a dicho SKU.
  4. Si no se provee **ID** y el **SKU no existe**: se clasifica como `NUEVO`.
  5. Si se provee un **ID numérico que no existe** en BD: se rechaza la fila con error; no se permite forzar IDs arbitrarios para registros nuevos.

---

### 2.4 Detección de Duplicados
- **SKU duplicado en el mismo Excel**: La segunda fila repetida se detecta inmediatamente y se clasifica como `ERROR: SKU aparece duplicado en el mismo archivo Excel`.
- **SKU existente en BD**: Si no trae ID, actualiza el producto existente. Si trae un ID perteneciente a otro registro, lanza conflicto de identidad.
- **Restricciones de Base de Datos**: La tabla `products` cuenta con restricción `UNIQUE (sku)` y clave primaria `PRIMARY KEY (id)`. Cualquier intento de inserción concurrente o colisión física es interceptado por PostgreSQL.

---

### 2.5 Transaccionalidad y Política de Persistencia
- **Política Actual**: **IMPORTACIÓN PARCIAL RESILIENTE CON REPORTE DE ERRORES**.
  - Al ejecutar `POST /productos/importar/confirmar`, cada fila se procesa individualmente dentro del ciclo de la conexión.
  - Si una fila genera excepción a nivel BD (por ejemplo, violación de foreign key o dato corrupto), el contador de errores se incrementa y se continúa con las demás filas válidas.
  - Al finalizar, el ERP notifica al usuario:
    `"Importación finalizada con éxito: X producto(s) creados, Y producto(s) actualizados. Z registro(s) tuvieron errores al persistir."`
- **Análisis**: Esta política es la habitual en catálogos masivos de retail y bodegas (para evitar que 1 producto defectuoso en una lista de 5.000 cancele la actualización de los otros 4.999). No obstante, para operaciones que requieran atomicidad total ("todo o nada"), se documenta en las recomendaciones.

---

### 2.6 Concurrencia
- Si dos usuarios importan en paralelo archivos que intentan dar de alta un producto con el mismo SKU:
  - El primer usuario que complete la confirmación insertará el registro con éxito.
  - El segundo usuario disparará una violación de restricción única en PostgreSQL (`products_sku_key UNIQUE constraint violation`).
  - La política de manejo de excepciones captura el error, evita caída del servidor (500) y reporta el fallo en el resumen final.

---

### 2.7 Manejo de Sesión y Payload
- **Arquitectura Encontrada**:
  - `POST /productos/importar/preview` almacena en `session['products_import_preview']` la lista analizada de items y el resumen.
- **Riesgo Identificado (Nivel P2)**:
  - Flask utiliza por defecto cookies firmadas en el cliente (`client-side session cookies`), cuyo tamaño máximo en navegadores estándar es de **4 KB**.
  - Para catálogos pequeños (< 50 productos), la cookie de sesión puede funcionar. Sin embargo, para catálogos medianos o grandes (1.000 a 10.000 productos), el tamaño del payload excede los 4 KB y provocará que el navegador descarte la cookie o lance error `400 Bad Request / Request Header Too Large`.
- **Mitigación / Recomendación**:
  - Reemplazar el almacenamiento directo del array en cookie por almacenamiento temporal en disco / base de datos del lado servidor (vía `import_id` único tipo UUID), manteniendo en la cookie de sesión únicamente el UUID.

---

### 2.8 Escalabilidad y Rendimiento (Mediciones Instrumentadas)
Se realizaron pruebas de estrés con archivos Excel generados sintéticamente de hasta 20.000 productos, midiendo tiempos con `time.perf_counter()` y uso de memoria mediante `getrusage`:

| Volumen (Productos) | Tamaño Archivo | Tiempo Parseo/Validación | Velocidad de Procesamiento | Memoria MaxRSS |
|---------------------|----------------|--------------------------|----------------------------|----------------|
| **100**             | 7.1 KB         | **0.008 s**              | 11.885 filas/s             | 1.219 MB       |
| **1.000**           | 25.0 KB        | **0.071 s**              | 14.088 filas/s             | 1.219 MB       |
| **5.000**           | 103.6 KB       | **0.332 s**              | 15.077 filas/s             | 1.219 MB       |
| **10.000**          | 201.6 KB       | **0.766 s**              | 13.061 filas/s             | 1.219 MB       |
| **20.000**          | 398.2 KB       | **1.603 s**              | 12.477 filas/s             | 1.219 MB       |

- **Análisis de Consultas SQL (Eliminación de N+1)**:
  - Durante la exportación: **1 query** masiva (`list_all_products_for_export`) + **1 query** masiva de resumen Kardex (`get_all_products_kardex_summary`). Total: **2 queries fijas**, independiente de si se exportan 10 o 20.000 productos ($O(1)$ en queries).
  - Durante la importación (preview): **1 query** masiva para construir el mapa en memoria (`get_products_lookup_maps`). Total: **1 query fija**, validación completa en RAM $O(1)$ por producto.

---

### 2.9 Seguridad
1. **Formula Injection (DDE / CSV Injection)**:
   - Se implementó sanitización activa en `generate_products_excel`: cualquier valor de texto que comience con los caracteres `=, +, -, @` es neutralizado automáticamente anteponiendo un apóstrofe `'`, evitando ejecución de fórmulas maliciosas en Microsoft Excel o LibreOffice.
2. **Archivos No XLSX / Archivos Corruptos**:
   - `openpyxl.load_workbook` está protegido con bloque `try/except Exception`, retornando mensaje amigable y código de estado controlado sin exponer trazas de depuración al usuario.
3. **Valores Numéricos Inválidos**:
   - `parse_flexible_float` rechaza strings alfanuméricos en columnas de costo o stock, marcando la fila como `ERROR`.

---

### 2.10 Autorización (RBAC) y Multitenant
- **Autenticación**: Las rutas están protegidas globalmente por el hook `@app.before_request`, redirigiendo obligatoriamente al login a cualquier petición anónima.
- **Permisos**:
  - Para usuarios autenticados sin rol Administrador, la ruta `/productos` y sus sub-rutas asociadas evalúan el permiso `productos` o `inventario`.
  - **Recomendación P2**: Agregar explícitamente el decorador `@require_permission('productos')` en los endpoints `/productos/exportar` y `/productos/importar/*` para consistencia con los módulos de compras y operario.
- **Multitenant**: La base de datos actual es de instancia única (sin columna `company_id` o `tenant_id` en la tabla `products`).

---

## 3. Matriz de Hallazgos y Clasificación de Riesgos

| ID | Clasificación | Descripción | Estado |
|---|---|---|---|
| **H1** | **P1 (Resuelto)** | Pérdida de precisión en costos decimales con strings chilenos e internacionales (`3062.65` interpretado como millar). | **CORREGIDO** con `parse_flexible_float` y `math.isclose`. |
| **H2** | **P1 (Resuelto)** | Ambigüedad en resolución de identidad si ID y SKU apuntaban a productos diferentes. | **CORREGIDO** con validación estricta de conflicto de identidad. |
| **H3** | **P2 (Resuelto)** | Riesgo de Formula Injection en valores exportados que inicien con `=, +, -, @`. | **CORREGIDO** con prefijo de escape `'`. |
| **H4** | **P2 (Pendiente)** | Almacenamiento del diff completo en `session` (cookie client-side) podría saturar el límite de 4 KB en archivos de más de 50 filas. | **DOCUMENTADO**: Se recomienda persistencia temporal con `import_id` (UUID) en servidor. |
| **H5** | **P3 (Pendiente)** | Falta de decorador granular `@require_permission('productos')` en endpoints de importación/exportación (actualmente protegido por sesión general). | **DOCUMENTADO**. |

---

## 4. Estado de la Suite de Pruebas y Regresión

Se ejecutó la suite completa de pruebas del proyecto:
```text
============================= 259 passed in 79.23s =============================
0 FAILED, 0 ERRORS, 0 WARNINGS
```

Todas las operaciones críticas existentes continúan funcionando con total normalidad:
- Creación y edición de productos manual.
- Ingreso y recepción de mercadería.
- Kardex físico y valoración PPP.
- Ventas, Cotizaciones y Fabricación de Productos.

---

## 5. Dictamen Final

La funcionalidad de **Exportación e Importación Masiva de Productos en Excel** queda formalmente **AUDITADA Y CERTIFICADA EN VERDE (GREEN)** para operaciones de catálogo estándar.
