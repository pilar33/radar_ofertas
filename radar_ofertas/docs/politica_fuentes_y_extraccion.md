# Politica de fuentes y extraccion

Esta politica define que fuentes pueden automatizarse y bajo que condiciones. El objetivo es evitar tecnicas evasivas y priorizar fuentes confiables, permitidas y sostenibles.

## Semaforo de fuentes

### Verde

- API oficial disponible.
- Feed de productos disponible.
- CSV/Excel descargable.
- Catalogo publico permitido.
- Sitemap/datos estructurados permitidos.
- Acuerdo directo con proveedor.

### Amarillo

- Web publica sin API.
- No bloquea acceso basico.
- No requiere login.
- No tiene captcha.
- Robots.txt no prohibe explicitamente la ruta.
- Se puede consultar con baja frecuencia y respeto tecnico.
- Requiere revision manual antes de automatizar.

### Rojo

- Prohibe scraping.
- Bloquea crawlers.
- Requiere login.
- Usa captcha.
- Bloquea con 403 persistente.
- Sus terminos prohiben extraccion automatizada.
- Se debe usar alternativa: API, CSV, afiliados, acuerdo o carga asistida.

## Reglas operativas

- No usar bypass de captcha.
- No usar proxies para evadir bloqueos.
- No simular comportamiento engañoso.
- No sobrecargar sitios.
- Respetar robots.txt y terminos.
- Priorizar fuentes confiables y permitidas.
- Revisar manualmente fuentes amarillas antes de automatizar.
- Documentar decisiones tecnicas cuando una fuente se marca roja.

## Proceso antes de scraping

1. Registrar la fuente.
2. Auditar home, robots.txt y sitemap.
3. Revisar terminos manualmente.
4. Clasificar semaforo.
5. Registrar decision tecnica.
6. Elegir alternativa limpia si esta disponible: API, CSV/Excel, catalogo PDF, carga URL, afiliados o acuerdo.
7. Solo si corresponde, implementar conector controlado con baja frecuencia y validaciones estrictas.

Hasta completar estos pasos, no se debe hacer scraping productivo.
