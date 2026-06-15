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

La accion deja el extractor en `solo_preview=True`, con `max_paginas=1`, `max_productos=10` y `delay_segundos=2`. No procesa productos automaticamente.

## Habilitar manualmente un extractor guardado

1. Politica: semaforo amarillo o verde, scraping permitido, robots y terminos revisados, sin login ni captcha.
2. Conector: activo, respeta politica y sin revision manual pendiente.
3. Extractor: habilitado, solo preview, max_paginas 1, max_productos 10 y delay 2.
4. Ejecutar preview.
5. Revisar imagen, URL, precio lista, transferencia, tarjeta/cuotas y precio oportunidad antes de procesar.
6. Procesar pocos productos primero.
# Comparar productos entre fuentes

Generar sugerencias con `docker compose exec web python manage.py generar_sugerencias_matching --limite 200 --min-score 60`. Revisarlas en `/matching/productos/`; aceptar vincula los `ProductoFuente` al mismo `ProductoCanonico`, mientras que rechazar conserva la decision para no recrear el par.
