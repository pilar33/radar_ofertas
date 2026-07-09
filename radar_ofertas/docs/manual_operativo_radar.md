# Manual operativo preliminar

## Flujo recomendado

1. Probar una web desde `/laboratorio/mapeo-web/`.
2. Revisar productos detectados, precios e imagenes.
3. Guardar como extractor si la fuente esta habilitada por politica.
4. Ejecutar preview desde el extractor.
5. Seleccionar productos convenientes.
6. Procesar resultados seleccionados.
7. Revisar productos en `/curaduria/productos/`.
8. Corregir URL, imagen, titulo o precio reciente si hace falta.
9. Revisar duplicados en `/curaduria/duplicados/`.
10. Fusionar duplicados sin borrar historial.
11. Recalcular ranking en `/oportunidades/ranking/`.
12. Marcar candidatos de compra para seguimiento.
13. Exportar dataset o snapshot antes de redeploys importantes.

## Render con SQLite

Render con SQLite es staging/demo. Los datos pueden perderse en redeploy. Para dataset real usar SQL Server local o una base cloud persistente.

## Ganga Home y nuevas fuentes

Para Ganga Home o fuentes Tienda Nube:

- crear fuente rapida;
- auditar/revisar politica;
- usar laboratorio;
- guardar extractor;
- ejecutar preview limitado;
- procesar solo seleccionados;
- curar y exportar.

No se usa OpenAI, machine learning ni scraping masivo en esta etapa.

## Carga piloto real en SQL Server

La carga piloto real debe hacerse sobre SQL Server local con Docker. Render con SQLite queda solo como demo/staging y no debe usarse como dataset real.

### 1. Abrir entorno local

```bash
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py diagnosticar_base_datos
```

Confirmar que el diagnostico indique SQL Server y no SQLite.

### 2. Mapear Ganga Home

1. Abrir `/laboratorio/mapeo-web/`.
2. Pegar URL real de categoria/listado.
3. Analizar pagina.
4. Revisar titulo, URL, imagen, precio lista, transferencia, tarjeta/cuotas y precio oportunidad.
5. Guardar extractor.
6. Ejecutar preview.
7. Seleccionar maximo 20 productos.
8. Procesar seleccionados.

### 3. Curar datos

Usar:

- `/curaduria/dashboard/`
- `/curaduria/productos/`
- `/curaduria/duplicados/`
- `/dataset/validacion-piloto/`

Revisar productos sin imagen, sin URL real, sin precio oportunidad, duplicados probables y productos que requieren revision.

### 4. Recalcular ranking

```bash
docker compose exec web python manage.py recalcular_ranking_comercial
```

Luego revisar `/oportunidades/ranking/`.

### 5. Exportar dataset y backup

```bash
docker compose exec web python manage.py validar_dataset_piloto
docker compose exec web python manage.py exportar_dataset_completo --output data/exports/radar_dataset_piloto.zip
docker compose exec web python manage.py exportar_snapshot --output data/backups/snapshot_piloto_sqlserver.json
```

El dataset sirve para analisis externo. El snapshot sirve para resguardar datos de prueba antes de seguir trabajando.

No ejecutar `docker compose down -v` si se quieren conservar los datos del volumen `sqlserver_data`.

## Habilitar extractor guardado para preview controlado

Si un extractor queda guardado pero bloqueado por politica, usar primero el boton en:

```text
/extractores/<id>/
Habilitar para preview controlado
```

La accion configura solo modo preview:

- semaforo amarillo si estaba desconocido;
- `permite_scraping=True`;
- `robots_txt_revisado=True`;
- `terminos_revisados=True`;
- `requiere_login=False`;
- `tiene_captcha=False`;
- conector activo;
- extractor habilitado;
- `solo_preview=True`;
- `max_paginas=1`;
- `max_productos=100`;
- `delay_segundos=2`.

No procesa productos automaticamente. Despues de ejecutar preview, revisar resultados antes de seleccionar y procesar.

Para Ganga Home se puede reparar rapido desde comando:

```bash
docker compose exec web python manage.py reparar_extractor_gangahome
```

Si se edita desde admin manualmente, verificar:

- Fuente / Politica: semaforo amarillo, scraping permitido, robots y terminos revisados, sin login ni captcha.
- Conector: activo, respeta politica, sin revision manual pendiente.
- Extractor: dominio `gangahome.com.ar`, pagina prueba `https://www.gangahome.com.ar/cocina/`, habilitado y solo preview.

## Habilitar manualmente un extractor guardado

Checklist manual si no se usa el boton automatico:

1. Editar `PoliticaExtraccionFuente`:
   - semaforo amarillo o verde;
   - `permite_scraping=True`;
   - `robots_txt_revisado=True`;
   - `terminos_revisados=True`;
   - `requiere_login=False`;
   - `tiene_captcha=False`.
2. Editar `ConectorFuente`:
   - `estado=activo`;
   - `respeta_politica_fuente=True`;
   - `requiere_revision_manual=False`.
3. Editar `ConfiguracionExtractorWeb`:
   - `habilitado=True`;
   - `solo_preview=True`;
   - `max_paginas=1`;
   - `max_productos=100`;
   - `delay_segundos=2`.
4. Ejecutar preview.
5. Revisar resultados antes de procesar: imagen, URL, precio lista, transferencia, tarjeta/cuotas y precio oportunidad.
6. Procesar pocos productos primero.
# Comparar productos entre fuentes

1. Procesar productos confirmados de al menos dos fuentes.
2. Ejecutar `docker compose exec web python manage.py generar_sugerencias_matching --limite 200 --min-score 60`.
3. Abrir `/matching/productos/` y revisar primero nivel alto.
4. Comparar titulo, atributos, imagen, URL e historial.
5. Aceptar para vincular ambos productos al mismo `ProductoCanonico`, o rechazar para que el par no vuelva a generarse.
6. Revisar el resultado en `/productos-multifuente/` y recalcular ranking cuando corresponda.

El proceso siempre requiere confirmacion humana. No realiza scraping ni procesamiento automatico.
# Demanda estimada y señales de venta

La demanda estimada combina señales visibles e indirectas para priorizar productos. No equivale a ventas reales. `cantidad_vendida_visible` solo se completa cuando la fuente publica expresamente una cantidad vendida; si no existe ese dato queda en cero.

Se guardan vendidos visibles, reseñas, preguntas, calificación, etiquetas como “más vendido”, “destacado” o “tendencia”, stock visible, variación de stock, recurrencia en previews y aparición en varias fuentes. Una caída de stock es únicamente un indicio y nunca se registra como venta confirmada.

El `score_demanda` va de 0 a 100:

- Alta: señales fuertes, generalmente score 70 o superior.
- Media: evidencia comercial parcial, score entre 40 y 69.
- Baja: existen señales débiles o negativas.
- Desconocida: no hay información visible suficiente.

La demanda debe analizarse junto al precio oportunidad, margen, calidad de URL, imagen e historial. Demanda alta no convierte automáticamente un producto en buena compra si el precio o margen no son convenientes.

Recalcular:

```powershell
docker compose exec web python manage.py recalcular_demanda
docker compose exec web python manage.py recalcular_ranking_comercial
```

# Navegación por proceso

El menú sigue el flujo operativo:

1. Fuentes: alta, estado, auditorías, conectores y extractores.
2. Mapeo: laboratorio, importación, carga asistida y resultados preview.
3. Procesamiento: productos, multifuente, matching y duplicados.
4. Curaduría: revisión de productos y previews.
5. Análisis comercial: ranking, demanda estimada y candidatos de compra.
6. Dataset: exportación, backup y validación piloto.
7. Configuración: base de datos, storage, política de scraping y administración.

# Habilitar manualmente un extractor guardado

1. Editar `PoliticaExtraccionFuente`: semáforo amarillo o verde, `permite_scraping=True`, `robots_txt_revisado=True`, `terminos_revisados=True`, `requiere_login=False` y `tiene_captcha=False`.
2. Editar `ConectorFuente`: `estado=activo`, `respeta_politica_fuente=True` y `requiere_revision_manual=False`.
3. Editar `ConfiguracionExtractorWeb`: `habilitado=True`, `solo_preview=True`, `max_paginas=1`, `max_productos=100` y `delay_segundos=2`.
4. Ejecutar preview.
5. Revisar los resultados antes de procesar.
6. Seleccionar y procesar pocos productos primero.

# Lotes de captura y trazabilidad

Un lote de captura identifica una ejecucion concreta y permite saber cuando, desde que fuente, URL, extractor o archivo se obtuvo cada dato. Se crea automaticamente al analizar una URL en el laboratorio, ejecutar un preview de extractor o procesar una importacion CSV/Excel. Tambien puede crearse manualmente con `crear_lote_manual`.

- Laboratorio: conserva los resultados detectados aunque sean una prueba.
- Extractor web: vincula ejecucion, resultados preview y los productos confirmados.
- Importacion: vincula archivo, filas, productos y precios creados o actualizados.
- Manual: sirve para documentar una carga controlada que no nace de esos flujos.

Abrir `/lotes-captura/`, revisar origen, URL, contadores, errores y detalles. Un lote correcto puede marcarse **Validado**. Un lote inutil debe marcarse **Descartado**, lo que lo deja no apto para dataset y excluido de ML. La accion **Excluir de ML** mantiene la trazabilidad y el uso operativo, pero evita que el export futuro de entrenamiento lo incluya. El CSV individual se descarga desde **Exportar CSV**.

No cargar datos masivos sin lote: se perderia la posibilidad de auditar errores, comparar capturas y separar pruebas de datos reales. Los lotes y sus fechas permiten agrupar precios y demanda por dia, mes o anio. Machine learning no se implementa en esta etapa; `apto_dataset`, `excluir_ml`, origen y fechas preparan el historial para modelos futuros de oportunidad y demanda.

Comandos:

```powershell
docker compose exec web python manage.py listar_lotes_captura
docker compose exec web python manage.py recalcular_lotes_captura
docker compose exec web python manage.py exportar_lote_captura --lote-id ID --output data/exports/lote_ID.csv
docker compose exec web python manage.py crear_lote_manual --fuente-id ID --nombre "Carga controlada" --tipo-carga piloto
```

# Flujo recomendado antes de cargar muchos datos

1. Diagnosticar la base SQL Server.
2. Crear un backup inicial.
3. Ejecutar laboratorio o extractor.
4. Revisar el lote generado.
5. Procesar pocos productos.
6. Validar el lote.
7. Curar productos y duplicados.
8. Recalcular el ranking.
9. Exportar el dataset.
10. Crear un backup final.

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

```powershell
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
