# Laboratorio de mapeo web

El laboratorio permite probar una pagina concreta de productos pegando una URL. Sirve para saber rapidamente si una fuente expone datos utiles antes de configurar un extractor completo.

## Que hace

- Hace un request controlado a una sola URL.
- No pagina automaticamente.
- No usa login, cookies, proxies ni captcha bypass.
- No procesa productos por defecto.
- Detecta senales de bloqueo, login o captcha.
- Detecta posible dependencia de JavaScript.
- Busca productos en JSON-LD y HTML.
- Sugiere selectores CSS cuando encuentra tarjetas de producto.
- Detecta multiples precios cuando la tarjeta expone lista, transferencia o tarjeta/cuotas.
- Calcula `precio_oportunidad` priorizando transferencia cuando aparece.
- Mejora la deteccion de imagenes con `src`, `data-src`, `srcset`, `data-srcset`, fondos CSS y atributos de CDN.

## JSON-LD

JSON-LD es informacion estructurada dentro del HTML, normalmente en scripts `application/ld+json`. Si contiene `Product` o `ItemList`, el laboratorio intenta extraer titulo, precio, URL, imagen y descripcion.

## Selectores CSS

Los selectores CSS indican donde esta cada dato en el HTML:

- `product_card_selector`: tarjeta o contenedor de producto.
- `title_selector`: titulo dentro de la tarjeta.
- `price_selector`: precio.
- `url_selector`: enlace al producto.
- `image_selector`: imagen.

Si el selector no encuentra elementos, puede estar mal mapeado o la pagina puede requerir JavaScript.

## Preset Tienda Nube

Cuando el HTML tiene senales de Tienda Nube, el laboratorio usa un preset conservador:

- tarjetas: `.js-item-product, .item-product`
- titulo: `.js-item-name, .item-name, [title], [aria-label]`
- precio: `.js-price-display, .price, [class*='price'], [class*='precio'], [class*='payment'], [class*='discount']`
- URL: enlaces a `/productos/`
- imagen: imagenes con `src`, `data-src`, `srcset`, `data-srcset` y variantes usadas por Tienda Nube

El preset evita tomar enlaces de menu, login, cuenta o carrito como productos.

## Multiprecio

El laboratorio y el extractor guardan estos datos cuando se detectan:

- `precio_lista`
- `precio_transferencia`
- `precio_tarjeta`
- `cuotas_texto`
- `precio_oportunidad`
- `tipo_precio_oportunidad`

`precio_oportunidad` usa transferencia si esta disponible. Si no hay transferencia, usa el menor precio total valido detectado. Los precios por cuotas se guardan como referencia, pero no se toman como precio total si el texto indica importe de cuota.

## Guardar extractor

Desde una sesion analizada se puede guardar la configuracion como `ConfiguracionExtractorWeb`. Si la fuente no tiene robots y terminos revisados, el extractor queda deshabilitado y en modo preview.

## Procesar productos

Solo se procesan resultados seleccionados explicitamente, con limite de 10 y si la fuente tiene politica habilitada para scraping controlado.

## URLs

- `/laboratorio/mapeo-web/`
- `/laboratorio/mapeo-web/ayuda/`
- `/fuentes/<id>/laboratorio/`

## Comandos

```bash
docker compose exec web python manage.py laboratorio_analizar_url --url "URL" --limite 10
docker compose exec web python manage.py laboratorio_analizar_url --url "URL" --limite 10 --preset tiendanube
docker compose exec web python manage.py laboratorio_guardar_extractor --url "URL" --fuente-id ID
```
