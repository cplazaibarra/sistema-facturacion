# Instrucciones para subir a GitHub

Este proyecto está listo para ser subido a GitHub. Sigue estos pasos:

## 1. Crear un repositorio en GitHub

1. Ve a https://github.com/new
2. Crea un nuevo repositorio con el nombre "Facturacion-Bodega-Miel"
3. NO inicialices con README, .gitignore ni licencia (ya los tenemos)
4. Haz clic en "Create repository"

## 2. Conectar el repositorio local con GitHub

Copia y ejecuta uno de estos comandos en la terminal (dentro de la carpeta del proyecto):

### Si el repositorio está vacío (recomendado):
```bash
git branch -M main
git remote add origin https://github.com/TU_USUARIO/Facturacion-Bodega-Miel.git
git push -u origin main
```

### Si prefieres usar SSH (requiere configuración previa):
```bash
git branch -M main
git remote add origin git@github.com:TU_USUARIO/Facturacion-Bodega-Miel.git
git push -u origin main
```

## 3. Autenticación

Si usas HTTPS, se te pedirá que ingreses:
- Usuario: Tu usuario de GitHub
- Contraseña: Un Personal Access Token (crear en GitHub > Settings > Developer settings > Personal access tokens)

## Commits posteriores

Para futuras actualizaciones, simplemente usa:
```bash
git add .
git commit -m "Descripción de los cambios"
git push
```

## Estado actual del proyecto

- ✅ Estructura base completada
- ✅ Menú de navegación con acceso a todas las páginas
- ✅ Sistema de administración de usuarios y roles
- ✅ Dashboard con gráficos
- ✅ Módulos: Inventario, Ventas, Productos, etc.

## Próximos pasos (después de subir a GitHub)

1. Migrar datos de ventas a la base de datos
2. Implementar filtros en datos de ventas
3. Agregar funcionalidades CRUD completas
4. Mejorar la interfaz de usuario
