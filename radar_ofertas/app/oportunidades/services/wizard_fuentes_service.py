from urllib.parse import urlparse

from oportunidades.models import ConectorFuente, ConfiguracionExtractorWeb, DecisionTecnica, FuenteWeb, PoliticaExtraccionFuente


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
