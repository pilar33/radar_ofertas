# Segunda fuente real

Etapa 3.10 agrega un flujo reutilizable para probar una segunda fuente real sin crear modelos nuevos.

## Flujo

1. Registrar fuente.
2. Auditar robots/home/sitemap.
3. Registrar revision manual de robots y terminos.
4. Crear conector borrador.
5. Configurar extractor y selectores.
6. Ejecutar preview controlado.
7. Rankear resultados.
8. Seleccionar los mejores.
9. Procesar solo resultados seleccionados si la politica lo permite.

## GangaHome

GangaHome queda como fuente candidata, pero la URL no se inventa. Se debe pasar explicitamente:

```bash
docker compose exec web python manage.py preparar_gangahome --url-base "URL_REAL"
```

El comando crea:

- `FuenteWeb`
- `PoliticaExtraccionFuente` en desconocido
- `ConectorFuente` borrador
- `ConfiguracionExtractorWeb` deshabilitada y en solo preview
- `DecisionTecnica`

No hace scraping.

## Estado operativo

```bash
docker compose exec web python manage.py estado_fuente --fuente-id ID
docker compose exec web python manage.py preview_fuente --fuente-id ID
```

Pantallas:

- `/fuentes/estado-operativo/`
- `/fuentes/<id>/estado-operativo/`
- `/extractores/resultados-pendientes/`

## Criterio

Si una fuente queda roja, requiere login, captcha, robots/terminos sin revisar o `permite_scraping=False`, el preview y procesamiento quedan bloqueados.
