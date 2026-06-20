import json
import re
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.db import transaction

from oportunidades.models import (
    CategoriaInteres,
    ConectorFuente,
    ConfiguracionExtractorWeb,
    FuenteWeb,
    PoliticaExtraccionFuente,
    PrecioFuente,
    Producto,
    ProductoCanonico,
    ResultadoLaboratorioMapeo,
    SesionLaboratorioMapeo,
)
from oportunidades.services.comparacion_service import calcular_comparacion_producto
from oportunidades.services.evaluacion_multifuente_service import evaluar_producto_multifuente
from oportunidades.services.demanda_service import (
    calcular_score_demanda,
    crear_o_actualizar_senal_demanda,
    extraer_senales_demanda_desde_card,
    extraer_senales_demanda_desde_texto,
)
from oportunidades.services.extractor_web_service import (
    detectar_plataforma_ecommerce,
    enriquecer_item_con_precios,
    extraer_css_productos,
    extraer_imagen_producto,
    extraer_precios_multiples_desde_card,
    extraer_json_ld_productos,
    extraer_titulo_producto,
    extraer_url_producto,
    normalizar_url_absoluta,
    obtener_preset_selectores_tiendanube,
    parsear_precio_web,
)
from oportunidades.services.importacion_service import (
    crear_o_actualizar_producto_fuente,
    crear_precio_fuente,
    obtener_o_crear_categoria_desde_texto,
    obtener_o_crear_producto_canonico,
)
from oportunidades.services.lotes_captura_service import (
    crear_lote_captura,
    finalizar_lote_captura,
    registrar_detalle_lote,
)
from oportunidades.services.dominios_service import normalizar_dominio


MAX_RESPONSE_BYTES = 1024 * 1024
HEADERS = {
    "User-Agent": "radar_ofertas/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}
CLASES_TARJETA = ["product", "producto", "item", "card", "grid", "collection", "catalog", "articulo", "article"]
BLOQUEOS_FUERTES = ["captcha", "g-recaptcha", "hcaptcha", "captcha challenge", "recaptcha", "cloudflare challenge", "access denied", "forbidden", "challenge"]
BLOQUEOS_LOGIN = ["debes iniciar sesion", "debes iniciar sesión", "contenido restringido", "acceso exclusivo"]


def normalizar_url_laboratorio(url):
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def _es_mercado_libre(url):
    dominio = urlparse(url).netloc.lower()
    return "mercadolibre." in dominio or "mercadolibre.com" in dominio or "meli." in dominio


def _config_temporal(url, modo="mixto"):
    parsed = urlparse(url)
    modo_map = {
        "auto": ConfiguracionExtractorWeb.MODO_MIXTO,
        "json_ld": ConfiguracionExtractorWeb.MODO_JSON_LD,
        "css": ConfiguracionExtractorWeb.MODO_CSS_SELECTORS,
        "css_selectors": ConfiguracionExtractorWeb.MODO_CSS_SELECTORS,
    }
    return SimpleNamespace(
        dominio_permitido=normalizar_dominio(parsed.netloc),
        modo_extraccion=modo_map.get(modo, ConfiguracionExtractorWeb.MODO_MIXTO),
        product_card_selector=None,
        title_selector=None,
        price_selector=None,
        url_selector=None,
        image_selector=None,
        description_selector=None,
    )


def _hacer_request_laboratorio(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15, stream=True, allow_redirects=True)
        chunks, total = [], 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_RESPONSE_BYTES:
                break
        texto = b"".join(chunks)[:MAX_RESPONSE_BYTES].decode(response.encoding or "utf-8", errors="replace")
        return {
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "content_type": (response.headers.get("Content-Type") or "").split(";")[0],
            "text": texto,
            "error": "" if response.status_code < 400 else f"HTTP {response.status_code}",
        }
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "content_type": "", "text": "", "error": str(exc)}


def detectar_bloqueos_laboratorio(html, productos_detectados=False):
    texto = (html or "").lower()
    bloqueos = [bloqueo for bloqueo in BLOQUEOS_FUERTES if bloqueo in texto]
    if not productos_detectados:
        bloqueos.extend([bloqueo for bloqueo in BLOQUEOS_LOGIN if bloqueo in texto])
    return bloqueos


def diagnosticar_js_laboratorio(html, productos):
    texto = (html or "").lower()
    soup = BeautifulSoup(html or "", "lxml")
    visible = soup.get_text(" ", strip=True)
    senales_js = ["__next_data__", "window.__", "app-root", "react", "vue", "angular"]
    return bool(not productos and (len(visible) < 250 or any(senal in texto for senal in senales_js)))


def _score_producto(item):
    score = 0
    if item.get("titulo"):
        score += 30
    precio = item.get("precio_oportunidad_decimal") or item.get("precio_decimal")
    if precio and precio > 0:
        score += 30
    if item.get("url_producto"):
        score += 20
    if item.get("imagen_url"):
        score += 10
    if item.get("descripcion"):
        score += 10
    return max(0, min(100, score))


def _normalizar_item(item, url_base):
    item = enriquecer_item_con_precios(item)
    precio_decimal = item.get("precio_decimal") or Decimal("0.00")
    mensaje_precio = ""
    normalizado = {
        "titulo": (item.get("titulo") or "").strip() or None,
        "precio_texto": (item.get("precio_texto") or "").strip() or None,
        "precio_decimal": precio_decimal or Decimal("0.00"),
        "precio_lista_texto": item.get("precio_lista_texto"),
        "precio_lista_decimal": item.get("precio_lista_decimal") or Decimal("0.00"),
        "precio_transferencia_texto": item.get("precio_transferencia_texto"),
        "precio_transferencia_decimal": item.get("precio_transferencia_decimal") or Decimal("0.00"),
        "precio_tarjeta_texto": item.get("precio_tarjeta_texto"),
        "precio_tarjeta_decimal": item.get("precio_tarjeta_decimal") or Decimal("0.00"),
        "cuotas_texto": item.get("cuotas_texto"),
        "precio_oportunidad_decimal": item.get("precio_oportunidad_decimal") or Decimal("0.00"),
        "tipo_precio_oportunidad": item.get("tipo_precio_oportunidad"),
        "texto_precios_detectado": item.get("texto_precios_detectado"),
        "url_producto": normalizar_url_absoluta(url_base, item.get("url_producto"), urlparse(url_base).netloc) if item.get("url_producto") else None,
        "imagen_url": normalizar_url_absoluta(url_base, item.get("imagen_url"), None) if item.get("imagen_url") else None,
        "descripcion": (item.get("descripcion") or "").strip() or None,
        "mensaje": mensaje_precio,
        "texto_demanda_detectado": item.get("texto_demanda_detectado"),
        "cantidad_vendida_visible": item.get("cantidad_vendida_visible", 0),
        "texto_vendidos": item.get("texto_vendidos"),
        "cantidad_resenas": item.get("cantidad_resenas", 0),
        "cantidad_preguntas": item.get("cantidad_preguntas", 0),
        "calificacion": item.get("calificacion", Decimal("0.00")),
        "etiqueta_mas_vendido": item.get("etiqueta_mas_vendido", False),
        "etiqueta_destacado": item.get("etiqueta_destacado", False),
        "etiqueta_tendencia": item.get("etiqueta_tendencia", False),
        "stock_visible": item.get("stock_visible", 0),
        "texto_stock": item.get("texto_stock"),
        "observaciones_demanda": item.get("observaciones"),
    }
    normalizado["score"] = _score_producto(normalizado)
    return normalizado


def _extraer_json_ld(html, url, config):
    productos = extraer_json_ld_productos(html, url, config)
    for item in productos:
        item.update(extraer_senales_demanda_desde_texto(" ".join(filter(None, [item.get("titulo"), item.get("descripcion")]))) )
    return [_normalizar_item(item, url) for item in productos if item.get("titulo") or item.get("precio_texto")]


def _parece_tarjeta(tag):
    clases = " ".join(tag.get("class", [])).lower()
    return any(palabra in clases for palabra in CLASES_TARJETA)


def _buscar_precio_texto(tag):
    for candidato in tag.find_all(["span", "div", "p", "strong", "b"]):
        texto = candidato.get_text(" ", strip=True)
        if "$" in texto or "ARS" in texto or re.search(r"\b\d{1,3}([.,]\d{3})+([,.]\d{2})?\b", texto):
            return texto[:100]
    texto = tag.get_text(" ", strip=True)
    match = re.search(r"(\$|ARS)?\s*\d{1,3}([.,]\d{3})+([,.]\d{2})?", texto)
    return match.group(0)[:100] if match else ""


def _extraer_css_heuristico(html, url, limite=30):
    soup = BeautifulSoup(html or "", "lxml")
    tarjetas = [tag for tag in soup.find_all(["article", "li", "div", "section"]) if _parece_tarjeta(tag)]
    productos = []
    for tarjeta in tarjetas[: limite * 5]:
        titulo = extraer_titulo_producto(tarjeta)
        precio_texto = _buscar_precio_texto(tarjeta)
        if not (titulo or precio_texto):
            continue
        item = {
            "titulo": titulo[:255],
            "precio_texto": precio_texto,
            "_precios_dom": extraer_precios_multiples_desde_card(tarjeta),
            "texto_precios_detectado": tarjeta.get_text(" ", strip=True),
            "url_producto": extraer_url_producto(tarjeta, url) or "",
            "imagen_url": extraer_imagen_producto(tarjeta, url),
            "descripcion": "",
            **extraer_senales_demanda_desde_card(tarjeta),
        }
        if not item["url_producto"] and (titulo or "").strip().lower() in {"menu", "inicio", "ver carrito", "registrate"}:
            continue
        productos.append(_normalizar_item(item, url))
    productos.sort(key=lambda item: item["score"], reverse=True)
    return productos[:limite]


def sugerir_selectores(html):
    if detectar_plataforma_ecommerce(html) == "tiendanube":
        return obtener_preset_selectores_tiendanube()
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup.find_all(["article", "li", "div", "section"]):
        if not _parece_tarjeta(tag):
            continue
        clases = tag.get("class") or []
        clase = next((c for c in clases if any(p in c.lower() for p in CLASES_TARJETA)), None)
        if not clase:
            continue
        selector = f".{clase}"
        if len(soup.select(selector)) < 1:
            continue
        return {
            "product_card_selector": selector,
            "title_selector": "h2, h3, h4, .title, .name, .product-title, .nombre, a",
            "price_selector": ".price, .precio, [class*=price], [class*=precio]",
            "url_selector": "a",
            "image_selector": "img",
            "mensaje": "Selectores sugeridos por clases de tarjeta.",
        }
    return {
        "product_card_selector": "",
        "title_selector": "",
        "price_selector": "",
        "url_selector": "",
        "image_selector": "",
        "mensaje": "No se pudieron sugerir selectores confiables.",
    }


def probar_selectores_laboratorio(html, url, selectores, limite=10):
    config = _config_temporal(url, "css_selectors")
    config.product_card_selector = selectores.get("product_card_selector")
    config.title_selector = selectores.get("title_selector")
    config.price_selector = selectores.get("price_selector")
    config.url_selector = selectores.get("url_selector")
    config.image_selector = selectores.get("image_selector")
    config.description_selector = selectores.get("description_selector")
    productos = extraer_css_productos(html, url, config)
    normalizados = [_normalizar_item(item, url) for item in productos[:limite]]
    return {
        "ok": bool(normalizados),
        "productos_detectados": normalizados,
        "mensaje": "Selectores aplicados." if normalizados else "El selector no encontro elementos. Revisa el HTML o puede requerir JavaScript.",
    }


def analizar_url_laboratorio(url, limite=10, modo="auto", selectores=None, preset=None):
    url = normalizar_url_laboratorio(url)
    limite = max(1, min(int(limite or 10), 30))
    if not url:
        return {"ok": False, "url": "", "status_code": None, "content_type": "", "plataforma_detectada": "desconocida", "requiere_js_probable": False, "bloqueos_detectados": [], "tiene_json_ld": False, "productos_detectados": [], "selectores_sugeridos": {}, "mensaje": "URL requerida.", "html_preview_limitado": ""}
    if _es_mercado_libre(url):
        return {"ok": False, "url": url, "status_code": None, "content_type": "", "plataforma_detectada": "mercado_libre", "requiere_js_probable": False, "bloqueos_detectados": ["mercado_libre_restringido"], "tiene_json_ld": False, "productos_detectados": [], "selectores_sugeridos": {}, "mensaje": "Mercado Libre esta restringido para scraping en este sistema.", "html_preview_limitado": ""}

    respuesta = _hacer_request_laboratorio(url)
    html = respuesta.get("text", "")
    plataforma = detectar_plataforma_ecommerce(html)
    if preset == "tiendanube":
        plataforma = "tiendanube"
    selectores_sugeridos = sugerir_selectores(html)
    if plataforma == "tiendanube":
        selectores_sugeridos = obtener_preset_selectores_tiendanube()
    config = _config_temporal(url, modo)
    productos = []
    if modo in {"auto", "json_ld"}:
        productos.extend(_extraer_json_ld(html, url, config))
    if modo == "css_selectors" and selectores:
        productos.extend(probar_selectores_laboratorio(html, url, selectores, limite)["productos_detectados"])
    elif plataforma == "tiendanube" and modo in {"auto", "css_selectors", "css"}:
        productos.extend(probar_selectores_laboratorio(html, url, selectores_sugeridos, limite)["productos_detectados"])
    elif modo in {"auto", "css_selectors", "css"}:
        productos.extend(_extraer_css_heuristico(html, url, limite=limite))
    productos = sorted(productos, key=lambda item: item["score"], reverse=True)[:limite]
    bloqueos = detectar_bloqueos_laboratorio(html, productos_detectados=bool(productos))
    tiene_json_ld = bool(BeautifulSoup(html or "", "lxml").find_all("script", attrs={"type": "application/ld+json"}))
    requiere_js = diagnosticar_js_laboratorio(html, productos)
    ok = respuesta["ok"] and not bloqueos
    mensaje = f"Analisis finalizado. Detectados={len(productos)}." if ok else respuesta.get("error") or "Analisis finalizado con advertencias."
    if bloqueos:
        mensaje = "Se detectaron senales de bloqueo/login/captcha."
    if requiere_js:
        mensaje += " La pagina parece requerir JavaScript."
    return {
        "ok": ok,
        "url": url,
        "status_code": respuesta.get("status_code"),
        "content_type": respuesta.get("content_type"),
        "plataforma_detectada": plataforma,
        "requiere_js_probable": requiere_js,
        "bloqueos_detectados": bloqueos,
        "tiene_json_ld": tiene_json_ld,
        "productos_detectados": productos,
        "selectores_sugeridos": selectores_sugeridos,
        "mensaje": mensaje,
        "html_preview_limitado": html[:5000],
    }


def crear_sesion_laboratorio(resultado, fuente_web=None):
    sesion = SesionLaboratorioMapeo.objects.create(
        url=resultado["url"],
        fuente_web=fuente_web,
        estado=SesionLaboratorioMapeo.ESTADO_ANALIZADA if resultado["ok"] else SesionLaboratorioMapeo.ESTADO_ERROR,
        status_code=resultado.get("status_code"),
        requiere_js_probable=resultado.get("requiere_js_probable", False),
        tiene_json_ld=resultado.get("tiene_json_ld", False),
        bloqueos_detectados=json.dumps(resultado.get("bloqueos_detectados", []), ensure_ascii=True),
        selectores_sugeridos=json.dumps(resultado.get("selectores_sugeridos", {}), ensure_ascii=True),
    )
    lote = crear_lote_captura(
        origen="laboratorio",
        fuente_web=fuente_web,
        sesion_laboratorio=sesion,
        url_origen=resultado["url"],
        tipo_carga="piloto",
        parametros={"status_code": resultado.get("status_code")},
    )
    for item in resultado.get("productos_detectados", []):
        demanda = calcular_score_demanda(item)
        resultado_laboratorio = ResultadoLaboratorioMapeo.objects.create(
            sesion=sesion,
            lote_captura=lote,
            titulo=item.get("titulo"),
            precio_texto=item.get("precio_texto"),
            precio_decimal=item.get("precio_decimal") or Decimal("0.00"),
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
            texto_demanda_detectado=item.get("texto_demanda_detectado"),
            score_demanda_preview=demanda["score"],
            nivel_demanda_preview=demanda["nivel"],
            url_producto=item.get("url_producto"),
            imagen_url=item.get("imagen_url"),
            descripcion=item.get("descripcion"),
            score=item.get("score", 0),
            seleccionado=item.get("score", 0) >= 70,
            mensaje=item.get("mensaje"),
        )
        registrar_detalle_lote(
            lote,
            "detectado",
            resultado_laboratorio=resultado_laboratorio,
            mensaje=item.get("mensaje"),
            datos_originales=item,
        )
    finalizar_lote_captura(lote, estado="procesado" if resultado["ok"] else "error")
    return sesion


def _politica_habilita(politica):
    return bool(
        politica
        and politica.semaforo in {PoliticaExtraccionFuente.SEMAFORO_VERDE, PoliticaExtraccionFuente.SEMAFORO_AMARILLO}
        and politica.permite_scraping
        and politica.robots_txt_revisado
        and politica.terminos_revisados
        and not politica.requiere_login
        and not politica.tiene_captcha
    )


def guardar_laboratorio_como_extractor(sesion, fuente_web=None, nombre_fuente="", rubro="", selectores=None, modo="auto"):
    url = sesion.url
    parsed = urlparse(url)
    url_base_real = f"{parsed.scheme}://{parsed.netloc}/"
    if not fuente_web:
        fuente_web, _ = FuenteWeb.objects.get_or_create(
            nombre=nombre_fuente or parsed.netloc,
            defaults={
                "url_base": url_base_real,
                "tipo_fuente": FuenteWeb.TIPO_TIENDA_ONLINE,
                "rubro_principal": rubro or None,
                "activa": True,
            },
        )
    if not fuente_web.url_base or "gangahome.example" in fuente_web.url_base:
        fuente_web.url_base = url_base_real
        fuente_web.save(update_fields=["url_base", "fecha_actualizacion"])
    politica, _ = PoliticaExtraccionFuente.objects.get_or_create(fuente=fuente_web)
    habilitado = _politica_habilita(politica)
    conector, _ = ConectorFuente.objects.get_or_create(
        fuente_web=fuente_web,
        nombre=f"{fuente_web.nombre} - Extractor laboratorio",
        defaults={
            "tipo_conector": ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            "estado": ConectorFuente.ESTADO_ACTIVO if habilitado else ConectorFuente.ESTADO_BORRADOR,
            "requiere_revision_manual": not habilitado,
            "respeta_politica_fuente": habilitado,
            "descripcion": "Conector creado desde laboratorio de mapeo web.",
        },
    )
    sugeridos = selectores or json.loads(sesion.selectores_sugeridos or "{}")
    modo_config = ConfiguracionExtractorWeb.MODO_MIXTO if modo == "auto" else modo
    extractor, _ = ConfiguracionExtractorWeb.objects.update_or_create(
        conector=conector,
        defaults={
            "url_inicio": fuente_web.url_base,
            "pagina_prueba_url": url,
            "url_categoria": url,
            "dominio_permitido": normalizar_dominio(parsed.netloc),
            "modo_extraccion": modo_config,
            "product_card_selector": sugeridos.get("product_card_selector") or None,
            "title_selector": sugeridos.get("title_selector") or None,
            "price_selector": sugeridos.get("price_selector") or None,
            "url_selector": sugeridos.get("url_selector") or None,
            "image_selector": sugeridos.get("image_selector") or None,
            "max_paginas": 1,
            "max_productos": 10,
            "delay_segundos": Decimal("2.00"),
            "habilitado": habilitado,
            "solo_preview": True,
            "requiere_js_detectado": sesion.requiere_js_probable,
            "observaciones": "Configuracion guardada desde laboratorio. Requiere auditoria si no esta habilitada.",
        },
    )
    sesion.fuente_web = fuente_web
    sesion.estado = SesionLaboratorioMapeo.ESTADO_GUARDADA
    sesion.save(update_fields=["fuente_web", "estado"])
    return extractor


@transaction.atomic
def procesar_resultados_laboratorio(sesion, limite=10):
    if not sesion.fuente_web:
        return {"ok": False, "procesados": 0, "errores": 1, "mensaje": "La sesion no tiene fuente asociada."}
    politica = getattr(sesion.fuente_web, "politica_extraccion", None)
    if not _politica_habilita(politica):
        return {"ok": False, "procesados": 0, "errores": 1, "mensaje": "La politica de la fuente bloquea el procesamiento."}
    resultados = sesion.resultados.filter(seleccionado=True, procesado=False).order_by("-score", "id")[: min(limite, 10)]
    if not resultados:
        return {"ok": False, "procesados": 0, "errores": 1, "mensaje": "No hay resultados seleccionados."}
    categoria = obtener_o_crear_categoria_desde_texto(sesion.fuente_web.rubro_principal, None)
    procesados = 0
    precios_creados = 0
    for resultado in resultados:
        row = {
            "titulo": resultado.titulo,
            "precio": resultado.precio_oportunidad_decimal or resultado.precio_decimal,
            "precio_lista": resultado.precio_lista_decimal,
            "precio_transferencia": resultado.precio_transferencia_decimal,
            "precio_tarjeta": resultado.precio_tarjeta_decimal,
            "cuotas_texto": resultado.cuotas_texto,
            "precio_oportunidad": resultado.precio_oportunidad_decimal or resultado.precio_decimal,
            "tipo_precio_oportunidad": resultado.tipo_precio_oportunidad,
            "url_producto": resultado.url_producto or sesion.url,
            "imagen_url": resultado.imagen_url,
            "descripcion": resultado.descripcion,
            "condicion": Producto.CONDICION_DESCONOCIDO,
            "moneda": sesion.fuente_web.moneda_principal,
            "origen_dato": PrecioFuente.ORIGEN_SCRAPING,
            "lote_captura": resultado.lote_captura,
        }
        producto_canonico, _ = obtener_o_crear_producto_canonico(row, categoria)
        producto_fuente, _, _ = crear_o_actualizar_producto_fuente(row, sesion.fuente_web, categoria, producto_canonico, actualizar=True)
        precio, precio_creado = crear_precio_fuente(producto_fuente, row, crear_si_no_cambio=False)
        calcular_comparacion_producto(producto_canonico)
        evaluar_producto_multifuente(producto_canonico)
        datos_demanda = extraer_senales_demanda_desde_texto(resultado.texto_demanda_detectado or "")
        crear_o_actualizar_senal_demanda(producto_fuente, datos_demanda, lote_captura=resultado.lote_captura)
        resultado.procesado = True
        resultado.save(update_fields=["procesado"])
        procesados += 1
        precios_creados += int(precio_creado)
        if resultado.lote_captura_id:
            registrar_detalle_lote(
                resultado.lote_captura,
                "procesado",
                producto_fuente=producto_fuente,
                precio_fuente=precio,
                resultado_laboratorio=resultado,
                mensaje="Resultado de laboratorio procesado.",
                datos_originales=row,
            )
            finalizar_lote_captura(resultado.lote_captura)
    sesion.estado = SesionLaboratorioMapeo.ESTADO_PROCESADA
    sesion.save(update_fields=["estado"])
    return {"ok": True, "procesados": procesados, "precios_creados": precios_creados, "errores": 0, "mensaje": "Resultados procesados."}
