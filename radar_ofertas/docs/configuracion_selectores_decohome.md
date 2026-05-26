# Configuracion de selectores Deco Home

## Objetivo

Esta etapa permite registrar revisiones manuales de terminos/robots, configurar selectores reales y ejecutar un preview controlado sobre una URL concreta. No procesa productos automaticamente y no hace scraping masivo.

## Revision manual

Antes de habilitar cualquier preview deben revisarse:

- terminos del sitio
- robots.txt
- restricciones comerciales o tecnicas

Comando de ejemplo:

```bash
docker compose exec web python manage.py registrar_revision_decohome --tipo terminos --resultado dudoso --url "URL" --resumen "Revision manual pendiente de definicion final" --decision "No habilitar scraping todavia" --aplicar
```

Si la revision prohibe automatizacion, la fuente pasa a semaforo rojo y `permite_scraping=False`.

## Encontrar selectores

Desde el navegador:

1. Abrir una pagina concreta de categoria o producto.
2. Inspeccionar una tarjeta de producto.
3. Copiar un selector estable para la tarjeta.
4. Copiar selectores internos para titulo, precio, URL e imagen.
5. Guardarlos en `/extractores/<id>/selectores/`.

Ejemplos orientativos:

```text
product_card_selector = .product-card
title_selector = .product-title
price_selector = .price
url_selector = a
image_selector = img
```

No inventar selectores: deben salir de una inspeccion real del HTML.

## Probar preview

Comandos:

```bash
docker compose exec web python manage.py configurar_selectores_decohome --pagina-prueba "URL"
docker compose exec web python manage.py probar_selectores_extractor --extractor-id ID
docker compose exec web python manage.py preview_decohome
```

URLs:

```text
http://localhost:8000/extractores/
http://localhost:8000/extractores/<id>/selectores/
http://localhost:8000/extractores/<id>/probar-selectores/
http://localhost:8000/fuentes/decohome/selectores/
```

## Interpretacion

- 0 productos detectados: revisar selectores, URL de prueba o modo JSON-LD.
- JSON-LD encontrado: puede ser suficiente sin selectores CSS.
- JS probable: el HTML inicial no contiene productos utiles y puede requerir renderizado JavaScript.
- 403/bloqueo/captcha/login: no continuar; revisar politica y alternativas.

## Limites

- No se pagina masivamente.
- No se procesa automaticamente.
- No se usan proxies.
- No se automatiza login.
- No se resuelven captchas.
- No se ignoran robots.txt ni terminos.

## Cuándo pasar a navegador headless

Solo considerar Playwright/Selenium si:

- la fuente queda verde o amarilla;
- robots y terminos estan revisados;
- no hay captcha ni login;
- el HTML inicial no trae productos;
- hay una decision tecnica que justifique el costo y el riesgo.
