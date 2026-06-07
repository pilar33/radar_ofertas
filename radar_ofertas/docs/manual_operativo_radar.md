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
