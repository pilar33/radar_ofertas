# Wizard de fuentes

El wizard permite registrar una fuente nueva sin crear modelos nuevos por cada sitio.

## Flujo

1. Registrar fuente.
2. Auditar home, robots.txt y sitemap.
3. Registrar revision manual de terminos y robots.
4. Crear conector en borrador.
5. Configurar extractor, URL de prueba y selectores.
6. Ejecutar preview controlado.
7. Seleccionar resultados.
8. Procesar seleccionados a productos multifuente.

## GangaHome

GangaHome puede cargarse con el mismo flujo, sin URL fija en el codigo:

```bash
docker compose exec web python manage.py preparar_fuente_generica --nombre "GangaHome" --url-base "URL" --rubro "hogar/deco"
```

El comando no activa scraping y deja la politica pendiente de revision.
