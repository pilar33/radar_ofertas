# Conectores por fuente

Un conector representa una forma controlada de alimentar la base multifuente desde una `FuenteWeb`.

## Tipos iniciales

- `csv_manual`
- `excel_manual`
- `csv_remoto`
- `excel_remoto`
- `api_oficial`
- `catalogo_pdf`
- `carga_url`
- `scraping_permitido`
- `otro`

## Conector permitido vs scraping

CSV/Excel, API oficial, catalogos entregados por proveedor y carga asistida por URL son conectores permitidos cuando la fuente o proveedor habilita ese uso.

`scraping_permitido` queda modelado pero no implementado. Antes de cualquier automatizacion se debe revisar semaforo, robots.txt, terminos, captcha, login y frecuencia.

## Relacion con semaforo

- Verde: API, CSV/Excel y carga URL pueden activarse si coinciden con la politica.
- Amarillo: requiere revision manual antes de automatizar.
- Rojo: no se activan conectores automaticos. Solo carga manual, URL o CSV/Excel autorizado cuando corresponda.

## Mercado Libre

Mercado Libre queda con conector API pausado porque OAuth funciona, pero catalogo, busqueda e items devuelven 403 por PolicyAgent.

## CSV/Excel

La importacion CSV/Excel puede vincularse a un `ConectorFuente` de tipo `csv_manual` o `excel_manual`. Si existe un conector activo para la fuente, el procesamiento intenta asociarlo automaticamente.

## Proximos pasos

- Crear primer conector especifico por fuente permitida.
- Agregar ejecuciones programadas cuando haya un proveedor con API/feed autorizado.
- Mantener scraping fuera del alcance hasta tener revision y permiso claro.
