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
- `max_productos=10`;
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
   - `max_productos=10`;
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
3. Editar `ConfiguracionExtractorWeb`: `habilitado=True`, `solo_preview=True`, `max_paginas=1`, `max_productos=10` y `delay_segundos=2`.
4. Ejecutar preview.
5. Revisar los resultados antes de procesar.
6. Seleccionar y procesar pocos productos primero.
