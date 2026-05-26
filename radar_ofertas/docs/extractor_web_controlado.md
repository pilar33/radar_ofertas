# Extractor web controlado

## Objetivo

El extractor web controlado permite hacer una prueba limitada y auditable sobre una fuente web real cuando la politica de la fuente lo permite. No reemplaza APIs, CSV/Excel ni acuerdos directos: esas alternativas siguen siendo preferidas.

## Preview y procesamiento

- Preview: detecta posibles productos y guarda `ResultadoExtraccionWeb`, pero no crea productos ni precios.
- Procesamiento: crea o actualiza `ProductoCanonico`, `ProductoFuente` y `PrecioFuente` a partir de resultados detectados. Solo se permite si la configuracion y la politica estan habilitadas.

Por defecto toda configuracion queda con `habilitado=False` y `solo_preview=True`.

## Condiciones para ejecutar

Un conector web solo puede ejecutarse si:

- `tipo_conector = scraping_permitido`
- `estado = activo`
- la fuente esta activa
- semaforo verde o amarillo
- `permite_scraping=True`
- `robots_txt_revisado=True`
- `terminos_revisados=True`
- `requiere_login=False`
- `tiene_captcha=False`
- `respeta_politica_fuente=True`
- `requiere_revision_manual=False`
- existe `ConfiguracionExtractorWeb`
- la configuracion esta habilitada

Si falta una condicion, la ejecucion se bloquea y registra un mensaje claro.

## Limites de esta etapa

- `max_paginas <= 3`
- `max_productos <= 50`
- `delay_segundos >= 1.5`
- respuesta HTML limitada a 1 MB
- sin reintentos agresivos
- sin cookies ni credenciales
- sin proxies
- sin navegador headless

Si el sitio requiere JavaScript para renderizar productos, se informa que no se implementa navegador headless en esta etapa.

## Modos de extraccion

- `json_ld`: busca datos estructurados `application/ld+json` de tipo `Product`.
- `css_selectors`: usa selectores CSS configurados manualmente.
- `mixto`: intenta JSON-LD y selectores CSS.
- `preview_manual`: configuracion inicial sin extraccion automatica efectiva.

## Selectores CSS

Para usar `css_selectors`, se deben configurar al menos:

- `product_card_selector`
- `title_selector`
- `price_selector`

Opcionales:

- `url_selector`
- `image_selector`
- `description_selector`
- `next_page_selector`

## Prohibiciones

- No automatizar login.
- No resolver captchas.
- No usar proxies para evadir bloqueos.
- No ignorar robots.txt ni terminos.
- No hacer scraping masivo.
- No hacer scraping de Mercado Libre.
- No automatizar compras ni publicaciones.

## Caso Deco Home

Comandos:

```bash
docker compose exec web python manage.py configurar_extractor_decohome
docker compose exec web python manage.py preview_decohome
docker compose exec web python manage.py ejecutar_extractor_web --conector-id ID
```

`configurar_extractor_decohome` deja la configuracion inicial en modo seguro:

- `habilitado=False`
- `solo_preview=True`
- `max_paginas=1`
- `max_productos=10`

Antes de habilitar el extractor se deben revisar manualmente terminos, robots.txt y selectores reales.

## Etapa 3.8 - Selectores y preview controlado

La etapa 3.8 agrega revision manual de terminos/robots, configuracion de `pagina_prueba_url`, diagnostico de HTML y prueba de selectores sin procesar productos.

El preview queda bloqueado si faltan:

- terminos revisados;
- robots revisado;
- semaforo verde o amarillo;
- `permite_scraping=True`;
- conector activo;
- configuracion habilitada.

Los resultados detectados se guardan como `ResultadoExtraccionWeb` y sirven para revisar muestras antes de decidir si una etapa futura debe procesarlos como `ProductoFuente`.
