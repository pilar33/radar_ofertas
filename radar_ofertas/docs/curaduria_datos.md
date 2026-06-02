# Curaduria de datos

La curaduria permite revisar productos procesados desde preview, laboratorio, importaciones o carga asistida.

Objetivos:

- Detectar productos con URL tecnica generada.
- Marcar productos que requieren revision.
- Reasignar un ProductoFuente a otro ProductoCanonico.
- Revisar historial de precios.
- Detectar posibles duplicados.
- Reprocesar previews sin duplicar productos.

URLs:

- `/curaduria/productos/`
- `/curaduria/previews/`
- `/oportunidades/ranking/`

Los productos sin URL real quedan marcados con `url_tecnica_generada=True` y `requiere_revision=True`.
