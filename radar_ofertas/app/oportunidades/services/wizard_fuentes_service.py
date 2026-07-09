from urllib.parse import urlparse

from oportunidades.models import ConectorFuente, ConfiguracionExtractorWeb, DecisionTecnica, FuenteWeb, PoliticaExtraccionFuente
from oportunidades.services.extractor_web_service import obtener_preset_selectores_tiendanube


def normalizar_url_base_wizard(url_base):
    url = (url_base or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    parsed = urlparse(url)
    if not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}/"


def crear_fuente_wizard(datos):
    url_base = normalizar_url_base_wizard(datos["url_base"])
    existente = FuenteWeb.objects.filter(url_base=url_base).first()
    if existente and existente.nombre != datos["nombre"]:
        fuente = existente
        creada = False
    else:
        fuente = None
        creada = False
    if fuente is None:
        fuente, creada = FuenteWeb.objects.get_or_create(
            nombre=datos["nombre"],
            defaults={
                "url_base": url_base,
                "tipo_fuente": datos.get("tipo_fuente") or FuenteWeb.TIPO_TIENDA_ONLINE,
                "rubro_principal": datos.get("rubro_principal") or None,
                "pais": datos.get("pais") or "Argentina",
                "moneda_principal": datos.get("moneda_principal") or "ARS",
                "activa": True,
            },
        )
    if not creada:
        fuente.url_base = url_base
        fuente.tipo_fuente = datos.get("tipo_fuente") or fuente.tipo_fuente
        fuente.rubro_principal = datos.get("rubro_principal") or fuente.rubro_principal
        fuente.pais = datos.get("pais") or fuente.pais
        fuente.moneda_principal = datos.get("moneda_principal") or fuente.moneda_principal
        fuente.save()
    PoliticaExtraccionFuente.objects.get_or_create(
        fuente=fuente,
        defaults={
            "semaforo": PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
            "metodo_preferido": PoliticaExtraccionFuente.METODO_PENDIENTE_REVISION,
            "permite_scraping": False,
            "robots_txt_revisado": False,
            "terminos_revisados": False,
        },
    )
    return fuente, creada


def _crear_fuente_wizard_legacy(datos):
    fuente, creada = FuenteWeb.objects.get_or_create(
        nombre=datos["nombre"],
        defaults={
            "url_base": datos["url_base"],
            "tipo_fuente": datos.get("tipo_fuente") or FuenteWeb.TIPO_TIENDA_ONLINE,
            "rubro_principal": datos.get("rubro_principal") or None,
            "pais": datos.get("pais") or "Argentina",
            "moneda_principal": datos.get("moneda_principal") or "ARS",
            "activa": True,
        },
    )
    if not creada:
        fuente.url_base = datos["url_base"]
        fuente.tipo_fuente = datos.get("tipo_fuente") or fuente.tipo_fuente
        fuente.rubro_principal = datos.get("rubro_principal") or fuente.rubro_principal
        fuente.pais = datos.get("pais") or fuente.pais
        fuente.moneda_principal = datos.get("moneda_principal") or fuente.moneda_principal
        fuente.save()
    PoliticaExtraccionFuente.objects.get_or_create(
        fuente=fuente,
        defaults={
            "semaforo": PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
            "metodo_preferido": PoliticaExtraccionFuente.METODO_PENDIENTE_REVISION,
            "permite_scraping": False,
            "robots_txt_revisado": False,
            "terminos_revisados": False,
        },
    )
    return fuente, creada


def preparar_fuente_generica(nombre, url_base, rubro="", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE):
    if not rubro:
        raise ValueError("El rubro es requerido para preparar una fuente generica.")
    fuente, creada = crear_fuente_wizard(
        {
            "nombre": nombre,
            "url_base": url_base,
            "rubro_principal": rubro,
            "tipo_fuente": tipo_fuente,
            "pais": "Argentina",
            "moneda_principal": "ARS",
        }
    )
    conector, conector_creado = ConectorFuente.objects.get_or_create(
        fuente_web=fuente,
        nombre=f"{fuente.nombre} - Conector web pendiente",
        defaults={
            "tipo_conector": ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            "estado": ConectorFuente.ESTADO_BORRADOR,
            "requiere_revision_manual": True,
            "respeta_politica_fuente": False,
            "descripcion": "Conector creado por wizard. No activar hasta revisar politica y selectores.",
        },
    )
    ConfiguracionExtractorWeb.objects.get_or_create(
        conector=conector,
        defaults={
            "url_inicio": fuente.url_base,
            "pagina_prueba_url": fuente.url_base,
            "dominio_permitido": urlparse(fuente.url_base).netloc,
            "modo_extraccion": ConfiguracionExtractorWeb.MODO_PREVIEW_MANUAL,
            "habilitado": False,
            "solo_preview": True,
            "observaciones": "Configuracion inicial creada por wizard. Completar politica y selectores antes de ejecutar.",
        },
    )
    DecisionTecnica.objects.get_or_create(
        titulo=f"Fuente preparada: {fuente.nombre}",
        categoria=DecisionTecnica.CATEGORIA_INTEGRACION,
        defaults={
            "descripcion": f"Se registro {fuente.nombre} como fuente candidata multifuente.",
            "decision": "Queda en estado pendiente hasta auditar robots, terminos y selectores.",
            "motivo": "Evitar automatizar fuentes sin politica revisada.",
            "impacto": "La fuente puede avanzar por wizard sin crear modelos nuevos.",
        },
    )
    return fuente, conector, creada, conector_creado


def _preset_por_plataforma(plataforma):
    if plataforma == "tiendanube":
        return obtener_preset_selectores_tiendanube()
    return {
        "product_card_selector": "",
        "title_selector": "",
        "price_selector": "",
        "url_selector": "",
        "image_selector": "",
        "description_selector": "",
    }


def crear_fuente_preview_rapida(datos):
    plataforma = datos.get("plataforma") or "auto"
    if plataforma == "auto":
        dominio = urlparse(datos["url_base"]).netloc.lower()
        plataforma = "tiendanube" if ".mitiendanube.com" in dominio or "gangahome" in dominio else "manual"

    fuente, conector, creada, conector_creado = preparar_fuente_generica(
        datos["nombre"],
        datos["url_base"],
        datos.get("rubro_principal") or "hogar/deco",
        FuenteWeb.TIPO_TIENDA_ONLINE,
    )
    politica, _ = PoliticaExtraccionFuente.objects.get_or_create(fuente=fuente)
    politica.semaforo = PoliticaExtraccionFuente.SEMAFORO_AMARILLO
    politica.metodo_preferido = PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO
    politica.permite_scraping = True
    politica.robots_txt_revisado = True
    politica.terminos_revisados = True
    politica.requiere_login = False
    politica.tiene_captcha = False
    politica.observaciones = (politica.observaciones or "") + "\nHabilitada desde fuente rapida solo para preview controlado."
    politica.save()
    fuente._state.fields_cache.pop("politica_extraccion", None)

    conector.estado = ConectorFuente.ESTADO_ACTIVO
    conector.respeta_politica_fuente = True
    conector.requiere_revision_manual = False
    conector.descripcion = conector.descripcion or "Conector de preview creado desde fuente rapida."
    conector.save()

    preset = _preset_por_plataforma(plataforma)
    extractor, _ = ConfiguracionExtractorWeb.objects.update_or_create(
        conector=conector,
        defaults={
            "url_inicio": fuente.url_base,
            "pagina_prueba_url": datos["url_categoria"],
            "url_categoria": datos["url_categoria"],
            "dominio_permitido": urlparse(fuente.url_base).netloc,
            "modo_extraccion": ConfiguracionExtractorWeb.MODO_MIXTO,
            "product_card_selector": preset.get("product_card_selector") or None,
            "title_selector": preset.get("title_selector") or None,
            "price_selector": preset.get("price_selector") or None,
            "url_selector": preset.get("url_selector") or None,
            "image_selector": preset.get("image_selector") or None,
            "description_selector": preset.get("description_selector") or None,
            "max_paginas": 1,
            "max_productos": 100,
            "delay_segundos": 2,
            "habilitado": True,
            "solo_preview": True,
            "observaciones": f"Extractor creado desde fuente rapida. Plataforma: {plataforma}.",
        },
    )
    return fuente, conector, extractor, creada, conector_creado, plataforma
