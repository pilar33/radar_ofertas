# Matching de productos entre fuentes

## Modelo de datos

`ProductoCanonico` representa el producto comparable: una identidad comun que agrupa publicaciones equivalentes. `ProductoFuente` conserva el titulo, URL, imagen y precios tal como aparecen en cada proveedor.

El matching hace falta porque dos fuentes pueden publicar el mismo articulo con nombres comerciales diferentes. `SugerenciaMatchingProducto` registra pares candidatos, score, motivos y decision humana sin borrar publicaciones ni historial.

## Calculo de similitud

El servicio normaliza texto, elimina ruido comercial y compara tokens. Tambien detecta cantidad, material, capacidad, medidas, color y codigo/modelo. El codigo suma mucho; cantidad, material y medidas refuerzan el resultado. La categoria y que sean fuentes distintas aportan contexto. El precio solo aplica una penalizacion moderada ante diferencias extremas.

- `80-100`: probabilidad alta.
- `60-79`: revision manual.
- `40-59`: similitud baja.
- Menos de `40`: descartar.

Generar un lote controlado:

```powershell
docker compose exec web python manage.py generar_sugerencias_matching --limite 200 --min-score 60
```

Se puede limitar con `--fuente-id` o incluir duplicados internos con `--incluir-misma-fuente`.

## Curaduria

Abrir `/matching/productos/`, filtrar pendientes y entrar a la comparacion. Aceptar vincula ambos `ProductoFuente` al mismo `ProductoCanonico`; tambien se puede elegir un canonico existente. Rechazar conserva la decision y evita que el par se recree automaticamente. Ignorar lo retira de la cola sin declararlo equivalente.

Al aceptar se registra `OperacionCuraduria`, se recalculan comparacion, evaluacion multifuente y ranking comercial. No se eliminan productos ni precios historicos.

## Comparacion y dataset

`/productos-multifuente/` muestra mejor precio oportunidad, promedio, fuente mas barata y diferencias porcentuales. El CSV incorpora grupo canonico, cantidad de fuentes, datos comparativos y estado del matching.

Estos campos forman etiquetas y variables auditables para una etapa futura de machine learning. La version actual no usa OpenAI ni modelos estadisticos.
