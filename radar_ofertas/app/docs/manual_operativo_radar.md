# Manual operativo preliminar

Ver tambien `docs/manual_operativo_radar.md` en la raiz del repositorio.

Flujo:

1. Probar web desde laboratorio.
2. Guardar extractor.
3. Ejecutar preview.
4. Seleccionar productos.
5. Procesar seleccionados.
6. Curar productos.
7. Revisar duplicados.
8. Consultar ranking comercial.
9. Exportar dataset o snapshot.

Render con SQLite es solo staging/demo.

## Carga piloto real en SQL Server

La carga piloto real debe hacerse en SQL Server local con Docker. No usar Render SQLite como dataset real.

Comandos:

```bash
docker compose exec web python manage.py diagnosticar_base_datos
docker compose exec web python manage.py flujo_piloto_fuente --fuente "Ganga Home" --limite 20
docker compose exec web python manage.py validar_dataset_piloto
docker compose exec web python manage.py recalcular_ranking_comercial
docker compose exec web python manage.py exportar_dataset_completo --output data/exports/radar_dataset_piloto.zip
docker compose exec web python manage.py exportar_snapshot --output data/backups/snapshot_piloto_sqlserver.json
```

Flujo:

1. Abrir laboratorio.
2. Mapear Ganga Home.
3. Verificar precios, imagen y URL.
4. Procesar seleccionados.
5. Curar datos.
6. Validar dataset piloto.
7. Exportar dataset y snapshot.

## Habilitar extractor guardado para preview controlado

Desde `/extractores/<id>/` usar el boton `Habilitar para preview controlado`.

Tambien se puede ejecutar:

```bash
docker compose exec web python manage.py reparar_extractor_gangahome
```

La accion deja el extractor en `solo_preview=True`, con `max_paginas=1`, `max_productos=100` y `delay_segundos=2`. No procesa productos automaticamente.

## Habilitar manualmente un extractor guardado

1. Politica: semaforo amarillo o verde, scraping permitido, robots y terminos revisados, sin login ni captcha.
2. Conector: activo, respeta politica y sin revision manual pendiente.
3. Extractor: habilitado, solo preview, max_paginas 1, max_productos 100 y delay 2.
4. Ejecutar preview.
5. Revisar imagen, URL, precio lista, transferencia, tarjeta/cuotas y precio oportunidad antes de procesar.
6. Procesar pocos productos primero.
# Comparar productos entre fuentes

Generar sugerencias con `docker compose exec web python manage.py generar_sugerencias_matching --limite 200 --min-score 60`. Revisarlas en `/matching/productos/`; aceptar vincula los `ProductoFuente` al mismo `ProductoCanonico`, mientras que rechazar conserva la decision para no recrear el par.
# Demanda estimada y señales de venta

La demanda estimada usa vendidos visibles, reseñas, preguntas, etiquetas, stock, recurrencia y aparición en varias fuentes. No inventa ventas: sin una cantidad publicada por la fuente, `cantidad_vendida_visible` queda en cero. Usar `/demanda/dashboard/` junto con ranking, precio y margen.

# Navegación por proceso

El menú agrupa Fuentes, Mapeo, Procesamiento, Curaduría, Análisis comercial, Dataset y Configuración.

# Habilitar manualmente un extractor guardado

Configurar política amarilla/verde con scraping, robots y términos revisados; activar el conector sin revisión manual; habilitar el extractor en `solo_preview` con una página, diez productos y dos segundos de demora. Ejecutar preview, revisar y procesar pocos productos.

# Lotes de captura y trazabilidad

Cada laboratorio, preview de extractor o importacion CSV/Excel crea un lote que conserva fuente, URL, fecha, origen, resultados, productos, precios, demanda y errores. Tambien se puede crear un lote manual. Revisar `/lotes-captura/`; validar los lotes correctos, descartar los inutiles y usar **Excluir de ML** cuando deban conservarse operativamente pero no incorporarse a un futuro entrenamiento.

El CSV individual se exporta desde el detalle o con:

```bash
docker compose exec web python manage.py exportar_lote_captura --lote-id ID --output data/exports/lote_ID.csv
```

No cargar datos masivos sin lote. Las fechas y relaciones permiten comparar precios por dia, mes y anio. Machine learning todavia no se implementa; estos metadatos preparan un dataset auditable para modelos futuros.

# Flujo recomendado antes de cargar muchos datos

1. Diagnosticar SQL Server.
2. Crear backup inicial.
3. Ejecutar laboratorio o extractor.
4. Revisar el lote.
5. Procesar pocos productos.
6. Validar el lote.
7. Curar productos.
8. Recalcular ranking.
9. Exportar dataset.
10. Crear backup final.

# Seguimiento comercial real

Una oportunidad detectada es una estimacion basada en precio, demanda y calidad de datos. Un resultado comercial real existe solamente cuando una persona registra la decision, la compra, la publicacion y la venta efectivamente realizadas.

Flujo operativo:

1. Detectar la oportunidad en el ranking y marcarla como candidato.
2. Revisar demanda, precio, URL, imagen, fuente y lote de captura.
3. Aprobar la compra o descartar el candidato indicando el motivo.
4. Si se compra, registrar fecha, unidades, precio unitario y todos los costos reales.
5. Registrar la publicacion de reventa, canal, cantidad y precio publicado.
6. Registrar cada venta real y sus comisiones, envio y otros costos.
7. Revisar el resultado comercial, unidades disponibles, ganancia y aprendizaje.
8. Usar estos resultados historicos para mejorar decisiones futuras.

El margen real se calcula sobre el costo total vendido, incluyendo envio de compra, comisiones y otros gastos. Omitir costos produce una rentabilidad ficticia. Al inicio se recomienda comprar pocas unidades, validar la rotacion y registrar siempre el descarte cuando se decide no comprar.

Abrir `/comercial/candidatos/` para el seguimiento y `/comercial/dashboard/` para el resumen. Estos datos preparan el dataset para futuro machine learning sobre conveniencia de compra, velocidad de venta, margen y riesgo. Machine learning no se implementa en esta etapa.

# Diferencia entre Preview, Procesamiento y Curaduria

Preview muestra productos detectados por laboratorio o extractor. Todavia no son productos definitivos: se revisan imagen, URL, precio lista, transferencia, tarjeta/cuotas, precio oportunidad, lote y advertencias. Desde `/extractores/<id>/resultados/` se seleccionan productos y se procesan masivamente con confirmacion.

Procesamiento crea o actualiza `ProductoFuente`, guarda `PrecioFuente`, vincula el lote de captura, conserva URL real, imagen, multiprecio y senales de demanda, y deja trazabilidad para auditoria y dataset. Los resultados sin precio oportunidad no se procesan.

Curaduria revisa calidad de productos ya procesados. Sirve para corregir URL tecnica, imagen faltante, lote faltante, precios incompletos, duplicados y aptitud de dataset. No deberia usarse como carga inicial producto por producto.

# Procesamiento masivo seguro

1. Abrir Resultados Preview.
2. Filtrar o revisar los productos procesables.
3. Usar **Seleccionar todos los procesables** o una seleccion mas especifica.
4. Revisar advertencias: URL tecnica, sin imagen, sin lote o sin precio.
5. Usar **Procesar seleccionados** o **Procesar todos los procesables del lote**.
6. Confirmar el procesamiento.
7. Ir a Curaduria.
8. Revisar productos con problemas.
9. Validar o descartar el lote desde `/lotes-captura/`.

Si aparecen productos con URL tecnica, ejecutar:

```bash
docker compose exec web python manage.py reparar_urls_productos_desde_preview --limite 50
```

El comando solo reemplaza URL tecnica cuando encuentra una URL real ya capturada en preview o laboratorio.

# Radar inteligente desde texto de ChatGPT

El Radar inteligente permite guardar oportunidades detectadas en texto pegado, por ejemplo desde una tarea de ChatGPT llamada Radar de Ofertas u otra fuente textual. La app no accede automaticamente a chats privados, no lee conversaciones de ChatGPT y no usa OpenAI API en esta etapa: la usuaria copia el bloque completo y lo pega manualmente en la app.

Flujo:

1. Abrir Radar de ChatGPT.
2. Copiar el bloque completo de oportunidad.
3. Ir a `/radar/importar-texto/`.
4. Pegar el texto.
5. Presionar **Analizar texto**.
6. Revisar el preview estructurado.
7. Importar todas las oportunidades validas o seleccionar cuales importar.
8. Abrir `/radar/ofertas/` para revisar oportunidades detectadas.
9. Marcar candidato de compra si corresponde.
10. Registrar compra, publicacion y venta luego si se concreta.

El parser intenta extraer tienda, producto, precio actual, comparable, descuento, motivo de conveniencia, chequeo anti-marketing, envio, stock, vendedor y URLs. Si un dato no aparece, queda vacio y la oportunidad se marca para revision. Siempre se conserva el texto original.

Las oportunidades se guardan en SQL Server local como `OportunidadRadar`, pueden vincularse a `ProductoFuente` o `ProductoCanonico`, pueden generar `CandidatoCompra`, y se exportan en `radar_oportunidades.csv` dentro del dataset completo. Una integracion automatica futura con OpenAI API o busqueda web queda pendiente y debera implementarse como etapa separada con permisos explicitos.
