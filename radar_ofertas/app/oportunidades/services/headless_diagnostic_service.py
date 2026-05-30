import os

from oportunidades.services.extractor_web_service import hacer_request_extractor, validar_ejecucion_extractor
from oportunidades.services.selector_preview_service import diagnosticar_html_para_extraccion


def headless_disponible():
    if os.getenv("ENABLE_HEADLESS_DIAGNOSTIC", "False") != "True":
        return {"disponible": False, "mensaje": "Diagnostico headless deshabilitado. Activar solo en entorno preparado.", "provider": "playwright"}
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        return {"disponible": False, "mensaje": "Playwright no esta instalado o no esta disponible.", "provider": "playwright"}
    return {"disponible": True, "mensaje": "Headless disponible para diagnostico controlado.", "provider": "playwright"}


def obtener_html_headless(url, config):
    disponibilidad = headless_disponible()
    if not disponibilidad["disponible"]:
        return {"ok": False, "html": "", "error": disponibilidad["mensaje"]}
    validacion = validar_ejecucion_extractor(config.conector)
    if not validacion["valido"]:
        return {"ok": False, "html": "", "error": validacion["mensaje"]}
    try:
        from playwright.sync_api import sync_playwright

        timeout = int(os.getenv("HEADLESS_TIMEOUT_SECONDS", "20")) * 1000
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            html = page.content()[:1024 * 1024]
            browser.close()
        return {"ok": True, "html": html, "error": ""}
    except Exception as exc:
        return {"ok": False, "html": "", "error": str(exc)}


def comparar_html_requests_vs_headless(config):
    url = config.pagina_prueba_url or config.url_categoria or config.url_inicio
    req = hacer_request_extractor(url, config)
    diag_req = diagnosticar_html_para_extraccion(req.get("text", "")) if req.get("text") else {}
    disponibilidad = headless_disponible()
    if not disponibilidad["disponible"]:
        return {
            "estado": "headless deshabilitado",
            "requests_ok": req.get("ok", False),
            "requests_len": len(req.get("text", "")),
            "requests_diagnostico": diag_req,
            "headless_ok": False,
            "headless_len": 0,
            "headless_diagnostico": {},
            "mensaje": disponibilidad["mensaje"],
        }
    head = obtener_html_headless(url, config)
    diag_head = diagnosticar_html_para_extraccion(head.get("html", "")) if head.get("html") else {}
    estado = "requests suficiente"
    if head.get("ok") and len(head.get("html", "")) > len(req.get("text", "")) * 1.5:
        estado = "headless mejora deteccion"
    if diag_req.get("requiere_js_probable"):
        estado = "requiere JS probable"
    return {
        "estado": estado,
        "requests_ok": req.get("ok", False),
        "requests_len": len(req.get("text", "")),
        "requests_diagnostico": diag_req,
        "headless_ok": head.get("ok", False),
        "headless_len": len(head.get("html", "")),
        "headless_diagnostico": diag_head,
        "mensaje": head.get("error", ""),
    }


def diagnosticar_requiere_headless(config):
    disponibilidad = headless_disponible()
    if not disponibilidad["disponible"]:
        return {
            "habilitado": False,
            "playwright_disponible": False,
            "provider": disponibilidad["provider"],
            "requiere_js_detectado": config.requiere_js_detectado,
            "mensaje": disponibilidad["mensaje"],
        }
    return {
        "habilitado": True,
        "playwright_disponible": True,
        "provider": disponibilidad["provider"],
        "requiere_js_detectado": config.requiere_js_detectado,
        "mensaje": "Listo para una etapa posterior con navegador headless controlado.",
    }
