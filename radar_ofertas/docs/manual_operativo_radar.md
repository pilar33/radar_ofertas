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
