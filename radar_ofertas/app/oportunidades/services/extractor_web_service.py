import hashlib
import json
import re
import time
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.utils.text import slugify

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
from oportunidades.services.dominios_service import url_pertenece_a_dominio


MAX_RESPONSE_BYTES = 1024 * 1024
HEADERS = {
    "User-Agent": "radar_ofertas/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}
TITULOS_INVALIDOS = {"menu", "inicio", "entendido", "cambiar cp", "ver carrito", "ingresa", "ingresá", "registrate", "mi cuenta"}
URLS_INVALIDAS = ["carrito", "cart", "login", "account", "cuenta", "checkout", "registr"]


def _sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto or "")) if not unicodedata.combining(c)).lower()


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
            if not url_pertenece_a_dominio(url, config.dominio_permitido):
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
    if dominio_permitido and not url_pertenece_a_dominio(absoluta, dominio_permitido):
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


def detectar_bloqueos_html(html, productos_detectados=False):
    texto = (html or "").lower()
    captcha = ["captcha", "g-recaptcha", "hcaptcha", "captcha challenge", "recaptcha"]
    acceso = ["access denied", "forbidden", "contenido restringido", "acceso exclusivo"]
    infraestructura = ["cloudflare challenge", "challenge-platform", "cf-chl"]
    if any(p in texto for p in captcha + infraestructura + acceso):
        return True
    if productos_detectados:
        return False
    texto_visible = BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)
    login_generico = ["debes iniciar sesion", "iniciar sesion", "mi cuenta"]
    return any(p in _sin_acentos(texto_visible) for p in login_generico) and len(texto_visible) < 250


def detectar_plataforma_ecommerce(html):
    texto = (html or "").lower()
    if any(
        senal in texto
        for senal in [
            "js-product-item",
            "js-item-product",
            "js-product-item-image-link-private",
            "data-nuvemshop",
            "mitiendanube.com",
            "product_grid_item",
            "js-price-display",
            "js-payment-discount",
            "nuvemshop",
        ]
    ):
        return "tiendanube"
    if "cdn.shopify.com" in texto or "shopify" in texto:
        return "shopify"
    if "woocommerce" in texto or "wp-content/plugins/woocommerce" in texto:
        return "woocommerce"
    return "desconocida"


def obtener_preset_selectores_tiendanube():
    return {
        "product_card_selector": ".js-item-product, .item-product",
        "title_selector": ".js-item-name, .item-name, [title], [aria-label]",
        "price_selector": ".js-item-price-container, .item-price-container, .price-container, .payment-discount-price-product-container, .ts-custom-discount, .js-max-installments-container",
        "url_selector": "a.js-product-item-image-link-private[href*='/productos/'], a.js-product-item-image-link-private[href*='/producto/'], a[href*='/productos/'], a[href*='/producto/']",
        "image_selector": "img.js-product-item-image-private, img.item-image-featured, img[data-src], img[data-original], img[src], img[srcset], img[data-srcset]",
        "description_selector": "",
        "mensaje": "Preset Tienda Nube aplicado automaticamente.",
    }


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
        "imagen_url": normalizar_url_absoluta(url_base, image, None) if image else None,
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


def _fragmento_alrededor(texto, inicio, fin, ventana=80):
    return texto[max(0, inicio - ventana) : min(len(texto), fin + ventana)]


def extraer_precios_multiples_desde_texto(texto):
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()
    resultado = {
        "precio_lista_texto": None,
        "precio_lista_decimal": Decimal("0.00"),
        "precio_transferencia_texto": None,
        "precio_transferencia_decimal": Decimal("0.00"),
        "precio_tarjeta_texto": None,
        "precio_tarjeta_decimal": Decimal("0.00"),
        "cuotas_texto": None,
        "precio_oportunidad_decimal": Decimal("0.00"),
        "tipo_precio_oportunidad": PrecioFuente.TIPO_PRECIO_DESCONOCIDO,
        "texto_precios_detectado": texto[:1000] or None,
    }
    if not texto:
        return resultado

    patron = re.compile(
        r"(?:ARS\s*)?\$\s*\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?"
        r"|(?:ARS\s*)?\$\s*\d+(?:,\d{2})?"
        r"|\b\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?\b"
        r"|\b\d{4,}(?:,\d{2})?\b",
        flags=re.IGNORECASE,
    )
    candidatos = []
    for match in patron.finditer(texto):
        valor_texto = match.group(0).strip()
        decimal = parsear_precio_web(valor_texto)[0]
        if decimal <= 0:
            continue
        contexto_previo = _sin_acentos(texto[max(0, match.start() - 90) : match.start()])
        contexto_posterior = _sin_acentos(texto[match.end() : min(len(texto), match.end() + 45)])
        contexto_total = f"{contexto_previo} {contexto_posterior}"
        if decimal < Decimal("1000") and "$" not in valor_texto and "ars" not in _sin_acentos(valor_texto):
            if any(palabra in contexto_total for palabra in ["cuota", "off", "%", "descuento"]):
                continue
        candidatos.append(
            {
                "texto": valor_texto,
                "decimal": decimal,
                "contexto": contexto_total,
                "contexto_previo": contexto_previo,
            }
        )

    cuota_match = re.search(r"\d+\s+cuotas?.{0,80}?\$?\s*\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?", texto, flags=re.IGNORECASE)
    if cuota_match:
        resultado["cuotas_texto"] = cuota_match.group(0).strip()[:200]

    totalizables = []
    for candidato in candidatos:
        contexto = candidato.get("contexto_previo", "")
        es_cuota = "cuota" in contexto or "sin interes" in contexto
        es_transferencia = "transferencia" in contexto or "efectivo" in contexto or "deposito" in contexto
        es_tarjeta = "tarjeta" in contexto or "credito" in contexto
        if es_transferencia and not resultado["precio_transferencia_decimal"]:
            resultado["precio_transferencia_texto"] = candidato["texto"]
            resultado["precio_transferencia_decimal"] = candidato["decimal"]
            totalizables.append((PrecioFuente.TIPO_PRECIO_TRANSFERENCIA, candidato["decimal"]))
        elif (es_tarjeta or es_cuota) and not resultado["precio_tarjeta_decimal"]:
            resultado["precio_tarjeta_texto"] = candidato["texto"]
            resultado["precio_tarjeta_decimal"] = candidato["decimal"]
            if not es_cuota:
                totalizables.append((PrecioFuente.TIPO_PRECIO_TARJETA, candidato["decimal"]))
        elif not resultado["precio_lista_decimal"]:
            resultado["precio_lista_texto"] = candidato["texto"]
            resultado["precio_lista_decimal"] = candidato["decimal"]
            totalizables.append((PrecioFuente.TIPO_PRECIO_LISTA, candidato["decimal"]))

    if not resultado["precio_lista_decimal"] and candidatos:
        candidato = candidatos[0]
        resultado["precio_lista_texto"] = candidato["texto"]
        resultado["precio_lista_decimal"] = candidato["decimal"]
        totalizables.append((PrecioFuente.TIPO_PRECIO_LISTA, candidato["decimal"]))

    if resultado["precio_transferencia_decimal"]:
        resultado["precio_oportunidad_decimal"] = resultado["precio_transferencia_decimal"]
        resultado["tipo_precio_oportunidad"] = PrecioFuente.TIPO_PRECIO_TRANSFERENCIA
    elif totalizables:
        tipo, precio = min(totalizables, key=lambda item: item[1])
        resultado["precio_oportunidad_decimal"] = precio
        resultado["tipo_precio_oportunidad"] = tipo
    elif resultado["precio_tarjeta_decimal"]:
        resultado["precio_oportunidad_decimal"] = resultado["precio_tarjeta_decimal"]
        resultado["tipo_precio_oportunidad"] = PrecioFuente.TIPO_PRECIO_TARJETA
    return resultado


SELECTORES_TRANSFERENCIA_TIENDANUBE = (
    ".payment-discount-price-product",
    ".payment-discount-price-product-container",
    ".ts-custom-discount",
    "[class*='payment-discount']",
    "[class*='discount-price']",
)
SELECTORES_PRECIO_LISTA_TIENDANUBE = (
    ".js-price-display",
    ".price",
    ".item-price",
    "[class*='price']",
)
SELECTORES_CUOTAS_TIENDANUBE = (
    ".js-max-installments-container",
    "[class*='installment']",
    "[class*='cuota']",
)


def _resultado_precios_vacio(texto=""):
    return {
        "precio_lista_texto": None,
        "precio_lista_decimal": Decimal("0.00"),
        "precio_transferencia_texto": None,
        "precio_transferencia_decimal": Decimal("0.00"),
        "precio_tarjeta_texto": None,
        "precio_tarjeta_decimal": Decimal("0.00"),
        "cuotas_texto": None,
        "precio_oportunidad_decimal": Decimal("0.00"),
        "tipo_precio_oportunidad": PrecioFuente.TIPO_PRECIO_DESCONOCIDO,
        "texto_precios_detectado": (texto or "")[:1000] or None,
    }


def _selectores(*selectores):
    return ", ".join(selectores)


def _esta_en_bloque_transferencia(elemento):
    if not elemento:
        return False
    selector = _selectores(*SELECTORES_TRANSFERENCIA_TIENDANUBE)
    return bool(elemento.select_one(selector) or elemento.find_parent(class_=re.compile(r"(payment-discount|discount-price|ts-custom-discount)")))


def _texto_bloque_cercano(elemento):
    if not elemento:
        return ""
    contenedor = elemento
    for ancestro in [elemento, *elemento.find_parents()[:3]]:
        texto = ancestro.get_text(" ", strip=True)
        if "transferencia" in _sin_acentos(texto):
            contenedor = ancestro
            break
    return contenedor.get_text(" ", strip=True)


def _primer_precio_desde_texto(texto):
    patron = re.compile(
        r"(?:ARS\s*)?\$\s*\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?"
        r"|(?:ARS\s*)?\$\s*\d+(?:,\d{2})?"
        r"|\b\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?\b"
        r"|\b\d{4,}(?:,\d{2})?\b",
        flags=re.IGNORECASE,
    )
    candidatos = [match.group(0) for match in patron.finditer(str(texto or ""))]
    valor = candidatos[-1] if "cuota" in _sin_acentos(texto) and candidatos else (candidatos[0] if candidatos else texto)
    precio, _ = parsear_precio_web(valor)
    return precio


def extraer_precios_multiples_desde_card(card):
    texto_card = card.get_text(" ", strip=True)
    resultado = _resultado_precios_vacio(texto_card)

    for bloque in card.select(_selectores(*SELECTORES_TRANSFERENCIA_TIENDANUBE)):
        texto_bloque = _texto_bloque_cercano(bloque)
        if "transferencia" not in _sin_acentos(texto_bloque):
            continue
        precio_el = bloque.select_one(".payment-discount-price-product") or bloque
        precio_texto = precio_el.get_text(" ", strip=True) or texto_bloque
        precio = _primer_precio_desde_texto(precio_texto)
        if precio <= 0:
            precio = _primer_precio_desde_texto(texto_bloque)
        if precio > 0:
            resultado["precio_transferencia_texto"] = texto_bloque[:150]
            resultado["precio_transferencia_decimal"] = precio
            break

    for precio_el in card.select(_selectores(*SELECTORES_PRECIO_LISTA_TIENDANUBE)):
        if _esta_en_bloque_transferencia(precio_el):
            continue
        texto_precio = precio_el.get_text(" ", strip=True)
        if not texto_precio or "cuota" in _sin_acentos(texto_precio):
            continue
        precio = _primer_precio_desde_texto(texto_precio)
        if precio > 0:
            resultado["precio_lista_texto"] = texto_precio[:100]
            resultado["precio_lista_decimal"] = precio
            break

    texto_cuotas = ""
    for cuotas_el in card.select(_selectores(*SELECTORES_CUOTAS_TIENDANUBE)):
        candidato = cuotas_el.get_text(" ", strip=True)
        if "cuota" in _sin_acentos(candidato):
            texto_cuotas = candidato
            break
    if not texto_cuotas:
        match = re.search(r"\d+\s+cuotas?.{0,80}?\$?\s*\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?", texto_card, flags=re.IGNORECASE)
        texto_cuotas = match.group(0).strip() if match else ""
    if texto_cuotas:
        resultado["cuotas_texto"] = texto_cuotas[:200]
        resultado["precio_tarjeta_texto"] = texto_cuotas[:150]
        resultado["precio_tarjeta_decimal"] = _primer_precio_desde_texto(texto_cuotas)

    if not resultado["precio_lista_decimal"] and not resultado["precio_transferencia_decimal"]:
        fallback = extraer_precios_multiples_desde_texto(texto_card)
        for campo, valor in fallback.items():
            if campo.startswith("precio_") and campo.endswith("_decimal"):
                if not resultado[campo] and valor:
                    resultado[campo] = valor
            elif not resultado.get(campo) and valor:
                resultado[campo] = valor

    if resultado["precio_transferencia_decimal"] > 0:
        resultado["precio_oportunidad_decimal"] = resultado["precio_transferencia_decimal"]
        resultado["tipo_precio_oportunidad"] = PrecioFuente.TIPO_PRECIO_TRANSFERENCIA
    else:
        candidatos = []
        if resultado["precio_lista_decimal"] > 0:
            candidatos.append((PrecioFuente.TIPO_PRECIO_LISTA, resultado["precio_lista_decimal"]))
        if resultado["precio_tarjeta_decimal"] > 0 and not resultado["cuotas_texto"]:
            candidatos.append((PrecioFuente.TIPO_PRECIO_TARJETA, resultado["precio_tarjeta_decimal"]))
        if candidatos:
            tipo, precio = min(candidatos, key=lambda item: item[1])
            resultado["precio_oportunidad_decimal"] = precio
            resultado["tipo_precio_oportunidad"] = tipo
        elif resultado["precio_tarjeta_decimal"] > 0:
            resultado["precio_oportunidad_decimal"] = resultado["precio_tarjeta_decimal"]
            resultado["tipo_precio_oportunidad"] = PrecioFuente.TIPO_PRECIO_TARJETA
    return resultado


def enriquecer_item_con_precios(item):
    if item.get("precio_oportunidad_decimal") or item.get("precio_transferencia_decimal") or item.get("precio_lista_decimal"):
        oportunidad = item.get("precio_oportunidad_decimal") or Decimal("0.00")
        item["precio_decimal"] = oportunidad if oportunidad > 0 else parsear_precio_web(item.get("precio_texto"))[0]
        return item
    datos = item.pop("_precios_dom", None)
    if not datos:
        datos = extraer_precios_multiples_desde_texto(
            " ".join(
                filter(
                    None,
                    [item.get("precio_texto"), item.get("texto_precios_detectado"), item.get("descripcion")],
                )
            )
        )
    item.update(datos)
    oportunidad = datos["precio_oportunidad_decimal"]
    item["precio_decimal"] = oportunidad if oportunidad > 0 else parsear_precio_web(item.get("precio_texto"))[0]
    return item


def _text(el):
    return el.get_text(" ", strip=True) if el else ""


def _url_imagen_desde_srcset(valor):
    if not valor:
        return ""
    partes = [parte.strip().split(" ")[0] for parte in valor.split(",") if parte.strip()]
    return partes[-1] if partes else ""


def extraer_imagen_producto(card, url_base):
    img = card.select_one(
        "img.js-product-item-image-private, img.item-image-featured, img[data-src], img[data-original], img[src], img[srcset], img[data-srcset]"
    ) or card.find("img")
    candidatos = []
    if img:
        for attr in ["src", "data-src", "data-original", "data-image"]:
            candidatos.append(img.get(attr))
        candidatos.append(_url_imagen_desde_srcset(img.get("srcset")))
        candidatos.append(_url_imagen_desde_srcset(img.get("data-srcset")))
    for tag in [card, *(card.find_all(True)[:20])]:
        style = tag.get("style") or ""
        match = re.search(r"background-image\s*:\s*url\(['\"]?([^'\")]+)", style)
        if match:
            candidatos.append(match.group(1))
        append_images = tag.get("data-append-images") or ""
        candidatos.extend(re.findall(r"https?://[^'\"\s]+(?:jpg|jpeg|png|webp)", append_images, flags=re.IGNORECASE))
        for valor in tag.attrs.values():
            if isinstance(valor, str):
                candidatos.extend(re.findall(r"https?://[^'\"\s]+(?:jpg|jpeg|png|webp)", valor, flags=re.IGNORECASE))
    for candidato in candidatos:
        if not candidato or str(candidato).startswith("data:image"):
            continue
        absoluta = normalizar_url_absoluta(url_base, str(candidato), None)
        if absoluta and re.search(r"\.(jpg|jpeg|png|webp)(\?|$)|mitiendanube|cdn-", absoluta, flags=re.IGNORECASE):
            return absoluta
    return ""


def extraer_url_producto(card, url_base):
    link = (
        card.select_one("a.js-product-item-image-link-private[href]")
        or card.select_one("a[href*='/productos/']")
        or card.find("a", href=True)
    )
    href = link.get("href") if link else card.get("href")
    absoluta = normalizar_url_absoluta(url_base, href or "", None)
    if not absoluta:
        return None
    path = urlparse(absoluta).path.lower()
    if any(invalida in path for invalida in URLS_INVALIDAS):
        return None
    if "/productos/" in path or "/producto/" in path or "/produto/" in path or re.search(r"/p/|/product", path):
        return absoluta
    return absoluta if link else None


def extraer_titulo_producto(card):
    candidatos = []
    for selector in [".js-item-name", ".item-name", "h2", "h3", "h4", "a.js-product-item-image-link-private", "a[href*='/productos/']", "a"]:
        el = card.select_one(selector)
        if not el:
            continue
        candidatos.extend([el.get_text(" ", strip=True), el.get("title"), el.get("aria-label")])
    for candidato in candidatos:
        texto = (candidato or "").strip()
        if texto and _sin_acentos(texto) not in TITULOS_INVALIDOS:
            return texto[:255]
    return ""


def extraer_css_productos(html, url_base, config):
    soup = BeautifulSoup(html or "", "lxml")
    cards = soup.select(config.product_card_selector) if config.product_card_selector else [soup]
    productos = []
    for card in cards:
        title_el = card.select_one(config.title_selector) if config.title_selector else None
        price_el = card.select_one(config.price_selector) if config.price_selector else None
        url_el = card.select_one(config.url_selector) if config.url_selector else title_el
        desc_el = card.select_one(config.description_selector) if config.description_selector else None
        titulo = _text(title_el) or extraer_titulo_producto(card)
        precio = _text(price_el)
        texto_precios = card.get_text(" ", strip=True)
        if not titulo and not precio:
            continue
        datos_precios = extraer_precios_multiples_desde_card(card)
        productos.append(
            enriquecer_item_con_precios(
                {
                    "titulo": titulo,
                    "precio_texto": precio,
                    "_precios_dom": datos_precios,
                    "texto_precios_detectado": texto_precios,
                    "url_producto": extraer_url_producto(card, url_base)
                    or normalizar_url_absoluta(url_base, url_el.get("href") if url_el else "", config.dominio_permitido),
                    "imagen_url": extraer_imagen_producto(card, url_base),
                    "descripcion": _text(desc_el),
                    "fuente_url": url_base,
                }
            )
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


def _url_producto_preview(fuente, resultado):
    if resultado.url_producto:
        return resultado.url_producto
    base = "|".join(
        [
            str(fuente.pk),
            _sin_acentos(resultado.titulo),
            str(resultado.precio_oportunidad_decimal or resultado.precio_decimal or ""),
            str(resultado.fuente_url or ""),
        ]
    )
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    slug = slugify(resultado.titulo or "producto")[:60] or "producto"
    return f"{fuente.url_base.rstrip('/')}/radar-preview/{slug}-{digest}"


def procesar_resultado_a_producto(resultado, conector):
    fuente = conector.fuente_web
    categoria = obtener_o_crear_categoria_desde_texto(None, None)
    codigo_preview = None
    if not resultado.url_producto:
        codigo_base = f"{fuente.pk}|{_sin_acentos(resultado.titulo)}|{resultado.precio_decimal}|{resultado.fuente_url or ''}"
        codigo_preview = f"preview-{hashlib.sha1(codigo_base.encode('utf-8')).hexdigest()[:12]}"
    row = {
        "titulo": resultado.titulo,
        "precio": resultado.precio_oportunidad_decimal or resultado.precio_decimal,
        "precio_lista": resultado.precio_lista_decimal,
        "precio_transferencia": resultado.precio_transferencia_decimal,
        "precio_tarjeta": resultado.precio_tarjeta_decimal,
        "cuotas_texto": resultado.cuotas_texto,
        "precio_oportunidad": resultado.precio_oportunidad_decimal,
        "tipo_precio_oportunidad": resultado.tipo_precio_oportunidad,
        "codigo_externo": codigo_preview,
        "url_producto": _url_producto_preview(fuente, resultado),
        "imagen_url": resultado.imagen_url,
        "descripcion": resultado.descripcion,
        "condicion": Producto.CONDICION_DESCONOCIDO,
        "moneda": fuente.moneda_principal,
        "origen_dato": PrecioFuente.ORIGEN_SCRAPING,
    }
    canonico, _ = obtener_o_crear_producto_canonico(row, categoria)
    producto_fuente, _, _ = crear_o_actualizar_producto_fuente(row, fuente, categoria, canonico, actualizar=True)
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
            item = enriquecer_item_con_precios(item)
            precio = item.get("precio_decimal") or Decimal("0.00")
            mensaje = ""
            resultado = ResultadoExtraccionWeb.objects.create(
                ejecucion=ejecucion,
                titulo=item.get("titulo"),
                precio_texto=item.get("precio_texto"),
                precio_decimal=precio,
                precio_lista_texto=item.get("precio_lista_texto"),
                precio_lista_decimal=item.get("precio_lista_decimal") or Decimal("0.00"),
                precio_transferencia_texto=item.get("precio_transferencia_texto"),
                precio_transferencia_decimal=item.get("precio_transferencia_decimal") or Decimal("0.00"),
                precio_tarjeta_texto=item.get("precio_tarjeta_texto"),
                precio_tarjeta_decimal=item.get("precio_tarjeta_decimal") or Decimal("0.00"),
                cuotas_texto=item.get("cuotas_texto"),
                precio_oportunidad_decimal=item.get("precio_oportunidad_decimal") or Decimal("0.00"),
                tipo_precio_oportunidad=item.get("tipo_precio_oportunidad") or PrecioFuente.TIPO_PRECIO_DESCONOCIDO,
                texto_precios_detectado=item.get("texto_precios_detectado"),
                url_producto=item.get("url_producto"),
                imagen_url=item.get("imagen_url"),
                descripcion=item.get("descripcion"),
                fuente_url=item.get("fuente_url") or url,
                mensaje=mensaje,
                raw_data=json.dumps(item, ensure_ascii=True, default=str),
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
