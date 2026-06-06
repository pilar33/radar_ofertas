# Flujo piloto de datos reales

Esta guia se usa para cargar una muestra real y limitada en SQL Server local. Render con SQLite queda solo como demo/staging.

## Antes de empezar

Confirmar que el entorno local usa SQL Server:

```bash
docker compose exec web python manage.py diagnosticar_base_datos
```

El resultado debe indicar:

- Engine: `mssql`
- Vendor: `microsoft`
- SQLite: `No`
- SQL Server: `Si`
- Persistente: `Si`

Si el diagnostico indica SQLite, no cargar dataset real.

## Piloto Ganga Home

1. Abrir `/laboratorio/mapeo-web/`.
2. Pegar una URL real de categoria/listado de Ganga Home.
3. Analizar pagina.
4. Verificar titulo, URL, imagen, precio lista, precio transferencia, tarjeta/cuotas, precio oportunidad y tipo oportunidad.
5. Guardar extractor si todavia no existe.
6. Ejecutar preview controlado.
7. Seleccionar como maximo 20 productos.
8. Procesar seleccionados.
9. Ir a `/curaduria/dashboard/`.
10. Revisar productos procesados.
11. Revisar duplicados en `/curaduria/duplicados/`.
12. Recalcular ranking.
13. Validar dataset piloto.
14. Exportar dataset y snapshot.

Comando guia:

```bash
docker compose exec web python manage.py flujo_piloto_fuente --fuente "Ganga Home" --limite 20
```

## Validacion posterior

```bash
docker compose exec web python manage.py validar_dataset_piloto
docker compose exec web python manage.py recalcular_ranking_comercial
docker compose exec web python manage.py exportar_dataset_completo --output data/exports/radar_dataset_piloto.zip
docker compose exec web python manage.py exportar_snapshot --output data/backups/snapshot_piloto_sqlserver.json
```

Vista:

```text
http://localhost:8000/dataset/validacion-piloto/
```

## Segunda fuente candidata

Para repetir el flujo con otra fuente:

1. Crear fuente desde wizard.
2. Auditar home, robots y sitemap.
3. Revisar terminos manualmente.
4. Mapear URL desde laboratorio.
5. Verificar precios e imagenes.
6. Guardar extractor.
7. Procesar pocos productos seleccionados.
8. Comparar contra Ganga Home.

No ejecutar scraping masivo ni paginar todo el sitio. La carga piloto busca validar calidad comercial, no volumen.
