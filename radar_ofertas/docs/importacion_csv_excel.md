# Importacion CSV/Excel

La Etapa 3.3 permite alimentar la base multifuente desde archivos CSV o Excel sin scraping y sin descargar paginas externas.

## Columnas minimas

- `titulo`
- `precio`

## Columnas opcionales

- `codigo_externo`
- `url_producto`
- `categoria`
- `marca`
- `descripcion`
- `imagen_url`
- `vendedor`
- `condicion`
- `disponible`
- `stock`
- `precio_lista`
- `descuento_porcentaje`
- `costo_envio`
- `moneda`

El sistema acepta variantes comunes como `title`, `producto`, `nombre`, `price`, `sku`, `link`, `brand`, `description` y `rubro`.

## Como importar

1. Crear o elegir una `FuenteWeb` activa.
2. Entrar a `/importaciones/nueva/`.
3. Subir un archivo `.csv`, `.xlsx` o `.xls`.
4. Elegir una categoria default si el archivo no trae categoria.
5. Procesar la importacion y revisar el resumen.

Plantilla: `docs/templates_importacion/productos_template.csv`.

## Duplicados

Para evitar duplicados, el sistema busca productos por:

1. `fuente_web + codigo_externo`
2. `fuente_web + url_producto`
3. `fuente_web + titulo normalizado`, cuando no hay codigo ni URL

Si encuentra un producto existente, lo actualiza solo cuando la opcion esta habilitada.

## Historial de precios

Se crea un `PrecioFuente` cuando:

- el producto no tenia precio previo;
- el precio cambio respecto del ultimo relevamiento;
- se activo la opcion de crear precio aunque no haya cambio.

## Alcance

Esta importacion no ejecuta codigo desde archivos, no hace scraping, no llama a URLs cargadas y no descarga paginas. CSV/Excel se considera una fuente verde cuando proviene de listas autorizadas, catalogos o proveedores.
