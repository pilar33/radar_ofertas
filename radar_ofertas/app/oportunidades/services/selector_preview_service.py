import json

from bs4 import BeautifulSoup
from django.utils import timezone

from oportunidades.models import ConfiguracionExtractorWeb, ResultadoExtraccionWeb
from oportunidades.services.conectores_service import crear_ejecucion_conector, finalizar_ejecucion_conector
from oportunidades.services.extractor_web_service import (
    detectar_bloqueos_html,
    extraer_css_productos,
    extraer_json_ld_productos,
    hacer_request_extractor,
    parsear_precio_web,
    validar_ejecucion_extractor,
)


def _guardar_resultado(ejecucion, item, url_base, estado=ResultadoExtraccionWeb.ESTADO_DETECTADO, mensaje=""):
    precio, precio_mensaje = parsear_precio_web(item.get("precio_texto"))
    return ResultadoExtraccionWeb.objects.create(
        ejecucion=ejecucion,
        titulo=item.get("titulo"),
        precio_texto=item.get("precio_texto"),
        precio_decimal=precio,
        url_producto=item.get("url_producto"),
        imagen_url=item.get("imagen_url"),
        descripcion=item.get("descripcion"),
        fuente_url=item.get("fuente_url") or url_base,
        estado=estado,
        mensaje=mensaje or precio_mensaje,
        raw_data=json.dumps(item, ensure_ascii=True),
    )


def probar_selectores_en_html(html, config, url_base):
    errores = []
    productos = []
    if config.modo_extraccion in {ConfiguracionExtractorWeb.MODO_CSS_SELECTORS, ConfiguracionExtractorWeb.MODO_MIXTO}:
        try:
            productos.extend(extraer_css_productos(html, url_base, config))
        except Exception as exc:
            errores.append(f"No se pudieron aplicar selectores CSS: {exc}")
    muestras = []
    for item in productos[:10]:
        precio, _ = parsear_precio_web(item.get("precio_texto"))
        muestras.append(
            {
                "titulo": item.get("titulo") or "",
                "precio_texto": item.get("precio_texto") or "",
                "precio_decimal": str(precio),
                "url_producto": item.get("url_producto") or "",
                "imagen_url": item.get("imagen_url") or "",
            }
        )
    return {
        "ok": bool(productos) and not errores,
        "productos_detectados": len(productos),
        "muestras": muestras,
        "errores": errores,
    }


def diagnosticar_html_para_extraccion(html):
    html = html or ""
    texto = html.lower()
    soup = BeautifulSoup(html, "lxml")
    scripts_ld = soup.find_all("script", attrs={"type": "application/ld+json"})
    tiene_json_ld = bool(scripts_ld)
    tiene_itemlist = any("itemlist" in (script.get_text() or "").lower() for script in scripts_ld)
    texto_visible = soup.get_text(" ", strip=True)
    senales = []
    for senal in ["__next_data__", "window.__", "app-root", "react", "vue", "angular"]:
        if senal in texto:
            senales.append(senal)
    if len(texto_visible) < 250:
        senales.append("contenido_html_escaso")
    if detectar_bloqueos_html(html):
        senales.append("bloqueo_login_captcha")
    tiene_productos_html_probable = bool(soup.select("[class*=product], [class*=producto], [class*=card], [itemtype*=Product]"))
    return {
        "requiere_js_probable": bool(senales) and not tiene_json_ld and not tiene_productos_html_probable,
        "tiene_json_ld": tiene_json_ld,
        "tiene_json_ld_itemlist": tiene_itemlist,
        "tiene_productos_html_probable": tiene_productos_html_probable,
        "senales": senales,
    }


def probar_url_preview(config):
    conector = config.conector
    validacion = validar_ejecucion_extractor(conector)
    ejecucion = crear_ejecucion_conector(conector)
    if not validacion["valido"]:
        config.ultimo_preview_ok = False
        config.ultimo_preview_mensaje = validacion["mensaje"]
        config.ultima_revision_selectores = timezone.now()
        config.save(update_fields=["ultimo_preview_ok", "ultimo_preview_mensaje", "ultima_revision_selectores"])
        ejecucion = finalizar_ejecucion_conector(
            ejecucion,
            {"errores": 1, "mensaje": validacion["mensaje"], "productos_detectados": 0},
        )
        return {
            "ok": False,
            "ejecucion": ejecucion,
            "productos_detectados": 0,
            "muestras": [],
            "errores": [validacion["mensaje"]],
            "diagnostico": {},
        }

    url = config.pagina_prueba_url or config.url_categoria or config.url_inicio
    respuesta = hacer_request_extractor(url, config)
    if not respuesta["ok"]:
        mensaje = respuesta.get("error") or "No se pudo obtener HTML para preview."
        config.ultimo_preview_ok = False
        config.ultimo_preview_mensaje = mensaje
        config.ultima_revision_selectores = timezone.now()
        config.save(update_fields=["ultimo_preview_ok", "ultimo_preview_mensaje", "ultima_revision_selectores"])
        ejecucion = finalizar_ejecucion_conector(ejecucion, {"errores": 1, "mensaje": mensaje})
        return {"ok": False, "ejecucion": ejecucion, "productos_detectados": 0, "muestras": [], "errores": [mensaje], "diagnostico": {}}

    html = respuesta["text"]
    diagnostico = diagnosticar_html_para_extraccion(html)
    productos = []
    errores = []
    if detectar_bloqueos_html(html):
        errores.append("El HTML contiene senales de bloqueo, login o captcha.")
    if config.modo_extraccion in {ConfiguracionExtractorWeb.MODO_JSON_LD, ConfiguracionExtractorWeb.MODO_MIXTO}:
        productos.extend(extraer_json_ld_productos(html, url, config))
    if config.modo_extraccion in {ConfiguracionExtractorWeb.MODO_CSS_SELECTORS, ConfiguracionExtractorWeb.MODO_MIXTO}:
        css = probar_selectores_en_html(html, config, url)
        productos.extend(css["muestras"])
        errores.extend(css["errores"])

    muestras = []
    for item in productos[: config.max_productos]:
        normalizado = {
            "titulo": item.get("titulo") or "",
            "precio_texto": item.get("precio_texto") or "",
            "url_producto": item.get("url_producto") or "",
            "imagen_url": item.get("imagen_url") or "",
            "descripcion": item.get("descripcion") or "",
            "fuente_url": item.get("fuente_url") or url,
        }
        muestras.append(normalizado)
        _guardar_resultado(ejecucion, normalizado, url)

    requiere_js = bool(diagnostico.get("requiere_js_probable")) and not muestras
    ok = bool(muestras) and not errores
    mensaje = (
        f"Preview finalizado. Detectados={len(muestras)}."
        if muestras
        else "No se detectaron productos. Revisar selectores o posible renderizado JavaScript."
    )
    if requiere_js:
        mensaje += " Requiere JS probable."
    config.requiere_js_detectado = requiere_js
    config.ultimo_preview_ok = ok
    config.ultimo_preview_mensaje = mensaje
    config.ultima_revision_selectores = timezone.now()
    config.save(
        update_fields=[
            "requiere_js_detectado",
            "ultimo_preview_ok",
            "ultimo_preview_mensaje",
            "ultima_revision_selectores",
        ]
    )
    ejecucion = finalizar_ejecucion_conector(
        ejecucion,
        {"productos_detectados": len(muestras), "errores": len(errores), "mensaje": mensaje},
    )
    return {
        "ok": ok,
        "ejecucion": ejecucion,
        "productos_detectados": len(muestras),
        "muestras": muestras,
        "errores": errores,
        "diagnostico": diagnostico,
    }
