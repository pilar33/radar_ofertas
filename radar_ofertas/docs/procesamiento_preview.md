# Procesamiento de resultados preview

Un resultado preview es una muestra detectada por un extractor web controlado. Primero queda en `ResultadoExtraccionWeb`; solo pasa a la base propia cuando una persona lo selecciona y confirma procesamiento.

## Cuándo se puede procesar

- Tiene titulo.
- Tiene precio mayor a cero.
- Tiene URL de producto o URL fuente.
- No fue procesado antes.
- La politica de la fuente permite ejecucion.
- La fuente no esta restringida como Mercado Libre.

## Qué se crea

- `ProductoCanonico` normalizado.
- `ProductoFuente` para la aparicion en la fuente.
- `PrecioFuente` si no hay precio previo o si cambio.
- `ComparacionPrecio` recalculada.
- `EvaluacionOportunidadMultifuente` recalculada.

## Antiduplicados

La clave principal es `fuente_web + url_producto`. Si no hay URL, se compara el titulo normalizado dentro de la misma fuente.

## Limites

En esta etapa se procesan hasta 20 resultados seleccionados por accion. No se pagina, no se procesa todo el sitio y no se publica nada automaticamente.
