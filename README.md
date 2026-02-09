# Sistema de Facturación - Bodega Miel

Aplicación web desarrollada con Python y Flask para la gestión de una bodega de productos de miel.

## Características

- **Dashboard**: Visualización de estadísticas, ventas y gráficos interactivos
- **Administración**: Gestión de usuarios, empresa y configuración del sistema
- **Inventario**: Control de productos, stock y categorías
- **Ingreso de Mercadería**: Registro de ingresos de productos al inventario
- **Proyección de Ventas**: Análisis y proyección de ventas futuras

## Requisitos

- Python 3.11+
- Conda (opcional, pero recomendado)
- Flask 3.0+

## Instalación

### Opción 1: Usando Conda (Recomendado)

1. Crear el ambiente conda:
```bash
conda create -n fac python=3.11 -y
```

2. Activar el ambiente:
```bash
conda activate fac
```

3. Instalar las dependencias:
```bash
pip install -r requirements.txt
```

### Opción 2: Usando venv

1. Crear ambiente virtual:
```bash
python -m venv .venv
```

2. Activar el ambiente:
- Windows:
```bash
.venv\Scripts\activate
```
- Linux/Mac:
```bash
source .venv/bin/activate
```

3. Instalar las dependencias:
```bash
pip install -r requirements.txt
```

## Ejecución

1. Asegúrate de tener el ambiente activado

2. Ejecuta la aplicación:
```bash
python app.py
```

3. Abre tu navegador en: http://localhost:5000

## Estructura del Proyecto

```
Facturacion-Bodega-miel/
│
├── app.py                 # Aplicación principal Flask
├── requirements.txt       # Dependencias del proyecto
├── README.md             # Este archivo
│
├── templates/            # Plantillas HTML
│   ├── base.html        # Template base
│   ├── dashboard.html   # Dashboard principal
│   ├── administracion.html
│   ├── inventario.html
│   ├── ingreso_mercaderia.html
│   └── proyeccion_ventas.html
│
└── static/              # Archivos estáticos
    └── css/
        └── style.css    # Estilos CSS personalizados
```

## Tecnologías Utilizadas

- **Backend**: Python 3.11, Flask 3.0
- **Frontend**: HTML5, CSS3, JavaScript
- **Gráficos**: Chart.js
- **Fuentes**: Google Fonts (Inter)

## Características de Diseño

- Interfaz moderna con paleta de colores azul/cyan
- Sidebar de navegación fijo
- Dashboard con tarjetas de estadísticas
- Gráficos interactivos (barras, donas, líneas)
- Diseño responsivo
- Animaciones y transiciones suaves

## API Endpoints

- `GET /` - Dashboard principal
- `GET /dashboard` - Dashboard principal
- `GET /administracion` - Panel de administración
- `GET /inventario` - Gestión de inventario
- `GET /ingreso-mercaderia` - Registro de ingresos
- `GET /proyeccion-ventas` - Proyección de ventas
- `GET /api/dashboard-data` - Datos JSON para el dashboard

## Desarrollo Futuro

- [ ] Integración con base de datos (SQLite/PostgreSQL)
- [ ] Sistema de autenticación de usuarios
- [ ] Generación de facturas PDF
- [ ] Reportes exportables (Excel, PDF)
- [ ] Sistema de notificaciones en tiempo real
- [ ] API REST completa
- [ ] Módulo de clientes
- [ ] Módulo de proveedores

## Licencia

Este proyecto es de código privado para uso interno.

## Autor

Desarrollado para Bodega Miel - 2026
