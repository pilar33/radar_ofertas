# Auditoria de fuentes web

La auditoria de fuentes web existe para decidir si una fuente puede integrarse de manera limpia antes de implementar cualquier extractor.

## Por que se hace antes de scraping

El radar debe priorizar APIs oficiales, CSV/Excel, catalogos, feeds, carga por URL y acuerdos. El scraping solo puede evaluarse si la fuente lo permite o no lo bloquea, y si no hay alternativas mas limpias.

## Que se revisa

- Home de la fuente y status HTTP.
- `robots.txt`.
- `sitemap.xml`.
- Senales de login, captcha, challenge o bloqueo.
- Recursos alternativos como CSV, Excel, PDF o feeds si estan claramente disponibles.
- Terminos de uso mediante revision manual.

## Semaforo

- Verde: API, CSV/Excel, feed, catalogo o permiso claro.
- Amarillo: web publica sin bloqueo fuerte, pero con revision pendiente.
- Rojo: bloqueo persistente, captcha, login obligatorio, terminos restrictivos o 403.
- Desconocido: informacion insuficiente.

## Caso Deco Home

Deco Home se registra como fuente candidata. La etapa 3.6 prepara la fuente, audita home/robots/sitemap y deja un conector web en borrador. No se extraen productos.

## Proxima etapa

La etapa 3.7 solo deberia implementar un extractor web controlado si la auditoria y la revision manual lo permiten. Si la fuente queda roja, se documenta y se elige otra fuente.
