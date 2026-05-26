import os


def headless_disponible():
    if os.getenv("ENABLE_HEADLESS_DIAGNOSTIC", "False") != "True":
        return {"disponible": False, "mensaje": "Diagnostico headless deshabilitado. Activar solo en entorno preparado."}
    try:
        import playwright  # noqa: F401
    except Exception:
        return {"disponible": False, "mensaje": "Playwright no esta instalado o no esta disponible."}
    return {"disponible": True, "mensaje": "Headless disponible para diagnostico controlado."}


def diagnosticar_requiere_headless(config):
    disponibilidad = headless_disponible()
    if not disponibilidad["disponible"]:
        return {
            "habilitado": False,
            "playwright_disponible": False,
            "requiere_js_detectado": config.requiere_js_detectado,
            "mensaje": disponibilidad["mensaje"],
        }
    return {
        "habilitado": True,
        "playwright_disponible": True,
        "requiere_js_detectado": config.requiere_js_detectado,
        "mensaje": "Listo para una etapa posterior con navegador headless controlado.",
    }
