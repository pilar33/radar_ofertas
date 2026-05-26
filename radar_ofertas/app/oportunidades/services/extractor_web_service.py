import json
import re
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from oportunidades.models import (
    ConfiguracionExtractorWeb,
    EjecucionConector,
    PoliticaExtraccionFuente,
    PrecioFuente,
    Producto,
    ProductoFuente,
    ResultadoExtraccionWeb,
)
from oportunidades.services.comparacion_service import calcular_comparacion_producto
from oportunidades.services.conectores_service import crear_ejecucion_conector, finalizar_ejecucion_conector
from oportunidades.services.evaluacion_multifuente_service import evaluar_producto_multifuente
from oportunidades.services.importacion_service import (
    crear_o_actualizar_producto_fuente,
    crear_precio_fuente,
    obtener_o_crear_categoria_desde_texto,
    obtener_o_crear_producto_canonico,
)


MAX_RESPONSE_BYTES = 1024 * 1024
HEADERS = {
    "User-Agent": "radar_ofertas/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}


def validar_ejecucion_extractor(conector):
    politica = getattr(conector.fuente_web, "politica_extraccion", None)
    try:
        config = conector.configuracion_web
    except ConfiguracionExtractorWeb.DoesNotExist:
        config = None
    if conector.tipo_conector != "scraping_permitido":
        return {"valido": False, "mensaje": "El conector no es scraping_permitido.", "nivel": "bloqueado"}
    if conector.estado != "activo":
        return {"valido": False, "mensaje": "El conector no esta activo.", "nivel": "bloqueado"}
    if not conector.fuente_web.activa:
        return {"valido": False, "mensaje": "La fuente no esta activa.", "nivel": "bloqueado"}
    if not politica:
        return {"valido": False, "mensaje": "La fuente no tiene politica.", "nivel": "bloqueado"}
    if politica.semaforo not in {PoliticaExtraccionFuente.SEMAFORO_VERDE, PoliticaExtraccionFuente.SEMAFORO_AMARILLO}:
        return {"valido": False, "mensaje": "Semaforo no habilitado para scraping.", "nivel": "bloqueado"}
    if not politica.permite_scraping:
        return {"valido": False, "mensaje": "La politica no permite scraping.", "nivel": "bloqueado"}
    if not politica.robots_txt_revisado:
        return {"valido": False, "mensaje": "robots_txt_revisado=False.", "nivel": "bloqueado"}
    if not politica.terminos_revisados:
        return {"valido": False, "mensaje": "terminos_revisados=False.", "nivel": "bloqueado"}
    if politica.requiere_login:
        return {"valido": False, "mensaje": "La fuente requiere login.", "nivel": "bloqueado"}
    if politica.tiene_captcha:
        return {"valido": False, "mensaje": "La fuente tiene captcha.", "nivel": "bloqueado"}
    if not conector.respeta_politica_fuente:
        return {"valido": False, "mensaje": "El conector no respeta politica de fuente.", "nivel": "bloqueado"}
    if conector.requiere_revision_manual:
        return {"valido": False, "mensaje": "La ejecucion requiere autorizacion manual explicita.", "nivel": "bloqueado"}
    if not config:
        return {"valido": False, "mensaje": "No existe ConfiguracionExtractorWeb.", "nivel": "bloqueado"}
    if not config.habilitado:
        return {"valido": False, "mensaje": "La configuracion del extractor no esta habilitada.", "nivel": "bloqueado"}
    if config.max_paginas > 3 or config.max_productos > 50 or config.delay_segundos < Decimal("1.50"):
        return {"valido": False, "mensaje": "Limites de paginas/productos/delay fuera de rango.", "nivel": "bloqueado"}
    for url in [config.pagina_prueba_url, config.url_inicio, config.url_categoria]:
        if url:
            parsed = urlparse(url)
            if parsed.netloc != config.dominio_permitido:
                return {"valido": False, "mensaje": "URL fuera del dominio permitido.", "nivel": "bloqueado"}
    return {"valido": True, "mensaje": "Extractor habilitado para ejecucion controlada.", "nivel": "ok"}


def obtener_condiciones_faltantes_extractor(conector):
    condiciones = []
    politica = getattr(conector.fuente_web, "politica_extraccion", None)
    try:
        config = conector.configuracion_web
    except ConfiguracionExtractorWeb.DoesNotExist:
        config = None

    if conector.tipo_conector != "scraping_permitido":
        condiciones.append("tipo_conector debe ser scraping_permitido")
    if conector.estado != "activo":
        condiciones.append("ConectorFuente.estado debe ser activo")
    if not conector.fuente_web.activa:
        condiciones.append("FuenteWeb.activa debe ser True")
    if not politica:
        condiciones.append("falta PoliticaExtraccionFuente")
    else:
        if politica.semaforo not in {PoliticaExtraccionFuente.SEMAFORO_VERDE, PoliticaExtraccionFuente.SEMAFORO_AMARILLO}:
            condiciones.append("semaforo debe ser verde o amarillo")
        if not politica.permite_scraping:
            condiciones.append("permite_scraping debe ser True")
        if not politica.robots_txt_revisado:
            condiciones.append("robots_txt_revisado debe ser True")
        if not politica.terminos_revisados:
            condiciones.append("terminos_revisados debe ser True")
        if politica.requiere_login:
            condiciones.append("requiere_login debe ser False")
        if politica.tiene_captcha:
            condiciones.append("tiene_captcha debe ser False")
    if not conector.respeta_politica_fuente:
        condiciones.append("respeta_politica_fuente debe ser True")
    if conector.requiere_revision_manual:
        condiciones.append("requiere_revision_manual debe ser False o autorizacion explicita")
    if not config:
        condiciones.append("falta ConfiguracionExtractorWeb")
    else:
        if not config.habilitado:
            condiciones.append("ConfiguracionExtractorWeb.habilitado debe ser True")
    return condiciones


def normalizar_url_absoluta(url_base, url, dominio_permitido=None):
    url = (url or "").strip()
    if not url or url.lower().startswith(("javascript:", "data:", "mailto:")):
        return None
    absoluta = urljoin(url_base, url)
    parsed = urlparse(absoluta)
    if dominio_permitido and parsed.netloc != dominio_permitido:
        return None
    return absoluta


def hacer_request_extractor(url, config):
    try:
        response = requests.get(url, headers=HEADERS, timeout=config.timeout_segundos, stream=True, allow_redirects=True)
        if response.status_code in {401, 403, 429}:
            return {"ok": False, "status_code": response.status_code, "content_type": "", "text": "", "error": f"Status bloqueante {response.status_code}."}
        chunks, total = [], 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_RESPONSE_BYTES:
                break
        text = b"".join(chunks)[:MAX_RESPONSE_BYTES].decode(response.encoding or "utf-8", errors="replace")
        return {
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "content_type": (response.headers.get("Content-Type") or "").split(";")[0],
            "text": text,
            "error": "",
        }
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "content_type": "", "text": "", "error": str(exc)}


def detectar_bloqueos_html(html):
    texto = (html or "").lower()
    return any(p in texto for p in ["captcha", "recaptcha", "cloudflare", "access denied", "forbidden", "iniciar sesión", "login", "robot", "challenge"])


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _producto_desde_json(obj, url_base, config):
    tipo = obj.get("@type")
    tipos = tipo if isinstance(tipo, list) else [tipo]
    if "Product" not in tipos:
        return None
    offers = obj.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    image = obj.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    return {
        "titulo": obj.get("name"),
        "precio_texto": str(offers.get("price") or ""),
        "url_producto": normalizar_url_absoluta(url_base, obj.get("url"), config.dominio_permitido),
        "imagen_url": normalizar_url_absoluta(url_base, image, config.dominio_permitido) if image else None,
        "descripcion": obj.get("description"),
        "fuente_url": url_base,
    }


def extraer_json_ld_productos(html, url_base, config):
    soup = BeautifulSoup(html or "", "lxml")
    productos = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.get_text() or "{}")
        except json.JSONDecodeError:
            continue
        for obj in _walk_json(data):
            producto = _producto_desde_json(obj, url_base, config)
            if producto and producto.get("titulo"):
                productos.append(producto)
    return productos


def _text(el):
    return el.get_text(" ", strip=True) if el else ""


def extraer_css_productos(html, url_base, config):
    soup = BeautifulSoup(html or "", "lxml")
    cards = soup.select(config.product_card_selector) if config.product_card_selector else [soup]
    productos = []
    for card in cards:
        title_el = card.select_one(config.title_selector) if config.title_selector else None
        price_el = card.select_one(config.price_selector) if config.price_selector else None
        url_el = card.select_one(config.url_selector) if config.url_selector else title_el
        image_el = card.select_one(config.image_selector) if config.image_selector else None
        desc_el = card.select_one(config.description_selector) if config.description_selector else None
        titulo = _text(title_el)
        precio = _text(price_el)
        if not titulo and not precio:
            continue
        productos.append(
            {
                "titulo": titulo,
                "precio_texto": precio,
                "url_producto": normalizar_url_absoluta(url_base, url_el.get("href") if url_el else "", config.dominio_permitido),
                "imagen_url": normalizar_url_absoluta(url_base, image_el.get("src") if image_el else "", config.dominio_permitido),
                "descripcion": _text(desc_el),
                "fuente_url": url_base,
            }
        )
    return productos


def parsear_precio_web(texto):
    texto = re.sub(r"[^0-9,.\-]", "", str(texto or ""))
    if not texto:
        return Decimal("0.00"), "Sin precio"
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".") if texto.rfind(",") > texto.rfind(".") else texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "." in texto and len(texto.split(".")[-1]) == 3:
        texto = texto.replace(".", "")
    try:
        return Decimal(texto).quantize(Decimal("0.01")), ""
    except (InvalidOperation, ValueError):
        return Decimal("0.00"), "Precio invalido"


def procesar_resultado_a_producto(resultado, conector):
    categoria = obtener_o_crear_categoria_desde_texto(None, None)
    row = {
        "titulo": resultado.titulo,
        "precio": resultado.precio_decimal,
        "url_producto": resultado.url_producto or conector.fuente_web.url_base,
        "imagen_url": resultado.imagen_url,
        "descripcion": resultado.descripcion,
        "condicion": Producto.CONDICION_DESCONOCIDO,
        "moneda": conector.fuente_web.moneda_principal,
        "origen_dato": PrecioFuente.ORIGEN_SCRAPING,
    }
    canonico, _ = obtener_o_crear_producto_canonico(row, categoria)
    producto_fuente, _, _ = crear_o_actualizar_producto_fuente(row, conector.fuente_web, categoria, canonico, actualizar=True)
    precio, _ = crear_precio_fuente(producto_fuente, row)
    calcular_comparacion_producto(canonico)
    evaluar_producto_multifuente(canonico)
    resultado.producto_fuente = producto_fuente
    resultado.estado = ResultadoExtraccionWeb.ESTADO_PROCESADO
    resultado.save(update_fields=["producto_fuente", "estado"])
    return producto_fuente, precio


def extraer_productos_preview(conector, procesar=False, max_productos=None, max_paginas=None):
    validacion = validar_ejecucion_extractor(conector)
    ejecucion = crear_ejecucion_conector(conector)
    if not validacion["valido"]:
        return finalizar_ejecucion_conector(ejecucion, {"estado": EjecucionConector.ESTADO_ERROR, "errores": 1, "mensaje": validacion["mensaje"]})
    config = conector.configuracion_web
    if procesar and config.solo_preview:
        return finalizar_ejecucion_conector(ejecucion, {"estado": EjecucionConector.ESTADO_ERROR, "errores": 1, "mensaje": "solo_preview=True bloquea procesamiento."})
    limite_productos = min(max_productos or config.max_productos, config.max_productos, 50)
    paginas = min(max_paginas or config.max_paginas, config.max_paginas, 3)
    urls = [config.url_categoria or config.url_inicio][:paginas]
    detectados = procesados = errores = 0
    for index, url in enumerate(urls):
        if index:
            time.sleep(float(config.delay_segundos))
        resp = hacer_request_extractor(url, config)
        if not resp["ok"]:
            errores += 1
            continue
        if detectar_bloqueos_html(resp["text"]):
            errores += 1
            break
        productos = []
        if config.modo_extraccion in {ConfiguracionExtractorWeb.MODO_JSON_LD, ConfiguracionExtractorWeb.MODO_MIXTO}:
            productos.extend(extraer_json_ld_productos(resp["text"], url, config))
        if config.modo_extraccion in {ConfiguracionExtractorWeb.MODO_CSS_SELECTORS, ConfiguracionExtractorWeb.MODO_MIXTO}:
            productos.extend(extraer_css_productos(resp["text"], url, config))
        if config.modo_extraccion == ConfiguracionExtractorWeb.MODO_PREVIEW_MANUAL and not productos:
            productos = []
        for item in productos[: max(0, limite_productos - detectados)]:
            precio, mensaje = parsear_precio_web(item.get("precio_texto"))
            resultado = ResultadoExtraccionWeb.objects.create(
                ejecucion=ejecucion,
                titulo=item.get("titulo"),
                precio_texto=item.get("precio_texto"),
                precio_decimal=precio,
                url_producto=item.get("url_producto"),
                imagen_url=item.get("imagen_url"),
                descripcion=item.get("descripcion"),
                fuente_url=item.get("fuente_url") or url,
                mensaje=mensaje,
                raw_data=json.dumps(item, ensure_ascii=True),
            )
            detectados += 1
            if procesar:
                procesar_resultado_a_producto(resultado, conector)
                procesados += 1
        if detectados >= limite_productos:
            break
    return finalizar_ejecucion_conector(
        ejecucion,
        {
            "productos_detectados": detectados,
            "productos_creados": procesados,
            "productos_actualizados": 0,
            "precios_creados": procesados,
            "errores": errores,
            "mensaje": f"Extractor finalizado. Detectados={detectados}, procesados={procesados}, errores={errores}.",
        },
    )
