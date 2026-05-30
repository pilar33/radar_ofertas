# Headless opcional controlado

El diagnostico headless queda preparado para casos donde una fuente publica no expone productos en HTML inicial y parece depender de JavaScript.

## Reglas

- Esta funcion esta deshabilitada por defecto con `ENABLE_HEADLESS_DIAGNOSTIC=False`.
- No se usa para scraping masivo.
- No procesa productos automaticamente.
- No usa login, cookies, proxies ni bypass de captcha.
- Solo compara una URL puntual configurada en el extractor.
- Si Playwright no esta instalado, el sistema debe seguir funcionando.

## Variables

```env
ENABLE_HEADLESS_DIAGNOSTIC=False
HEADLESS_PROVIDER=playwright
HEADLESS_TIMEOUT_SECONDS=20
HEADLESS_MAX_PAGES=1
HEADLESS_SCREENSHOTS=False
```

Para instalarlo manualmente en un entorno preparado:

```bash
pip install -r requirements-headless.txt
playwright install chromium
```

## Comandos

```bash
docker compose exec web python manage.py diagnosticar_headless_extractor --extractor-id ID
```

## Interpretacion

- `headless deshabilitado`: comportamiento esperado por defecto.
- `requests suficiente`: el HTML inicial alcanza para configurar selectores o JSON-LD.
- `requiere JS probable`: evaluar una etapa posterior con navegador headless controlado.
- `headless mejora deteccion`: el HTML renderizado aporta mas informacion, pero aun requiere aprobacion y limites.
