# Conector catalogo CSV/Excel

La Etapa 3.5 hace operativo el primer conector permitido: catalogos CSV/Excel. No implementa scraping, no descarga HTML y no intenta evadir restricciones.

## Objetivo

Procesar catalogos de precios provistos o autorizados por una fuente para alimentar `ProductoFuente`, `ProductoCanonico`, `PrecioFuente`, comparaciones y evaluaciones multifuente.

## Tipos

- `csv_manual`: procesa importaciones CSV cargadas manualmente.
- `excel_manual`: procesa importaciones Excel cargadas manualmente.
- `csv_remoto`: descarga una URL directa a un archivo CSV autorizado.
- `excel_remoto`: descarga una URL directa a un archivo XLSX/XLS autorizado.

## Por que es fuente verde

CSV/Excel es verde cuando proviene de listas autorizadas, catalogos de proveedor, exportaciones o acuerdos. La fuente debe estar documentada con politica `csv_excel` o el conector debe marcar `fuente_autorizo_uso=True`.

## Validaciones

- El conector debe ser CSV/Excel.
- La fuente debe estar activa.
- Si es remoto, debe tener `url_recurso`.
- La URL remota debe ser directa a `.csv`, `.xlsx` o `.xls`, o declarar formato.
- Se bloquean respuestas HTML.
- Se limita el archivo a 10 MB.
- En fuentes rojas, solo se permite descarga remota si el metodo es `csv_excel` y la fuente autorizo el uso.

## Proceso

1. Se crea una `EjecucionConector`.
2. Se valida politica y tipo de conector.
3. Si es remoto, se descarga el archivo con `requests` y se guarda con `default_storage`.
4. Se crea o vincula una `ImportacionProductos`.
5. Se procesa la importacion con `importacion_service`.
6. Se actualizan contadores y detalles de ejecucion.

## Relacion con ImportacionProductos

Las importaciones pueden tener `conector`. Si se ejecuta un conector manual, busca una importacion pendiente asociada. Si es remoto, crea una nueva importacion.

## No es scraping

El conector no descarga HTML, no parsea sitios web, no navega paginas, no usa proxies, no evita captcha y no accede a recursos con login. Solo procesa archivos CSV/Excel autorizados.

## Ejemplos

```bash
docker compose exec web python manage.py crear_conector_catalogo_demo
docker compose exec web python manage.py ejecutar_conector --conector-id 1
```

Vistas:

```text
/conectores/
/conectores/nuevo-catalogo/
/conectores/<id>/
```
