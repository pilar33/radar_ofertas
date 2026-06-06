from decimal import Decimal

from django.db.models import Q

from oportunidades.models import ConfiguracionExtractorWeb, ConectorFuente, FuenteWeb, PoliticaExtraccionFuente
from oportunidades.services.dominios_service import normalizar_dominio


GANGAHOME_URL_BASE = "https://www.gangahome.com.ar/"
GANGAHOME_URL_CATEGORIA = "https://www.gangahome.com.ar/cocina/"
GANGAHOME_DOMINIO = "gangahome.com.ar"


def habilitar_extractor_preview_controlado(extractor):
    fuente = extractor.conector.fuente_web
    politica, _ = PoliticaExtraccionFuente.objects.get_or_create(fuente=fuente)
    if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO:
        politica.semaforo = PoliticaExtraccionFuente.SEMAFORO_AMARILLO
    politica.permite_scraping = True
    politica.robots_txt_revisado = True
    politica.terminos_revisados = True
    politica.requiere_login = False
    politica.tiene_captcha = False
    politica.save(
        update_fields=[
            "semaforo",
            "permite_scraping",
            "robots_txt_revisado",
            "terminos_revisados",
            "requiere_login",
            "tiene_captcha",
        ]
    )

    conector = extractor.conector
    conector.estado = ConectorFuente.ESTADO_ACTIVO
    conector.respeta_politica_fuente = True
    conector.requiere_revision_manual = False
    conector.save(update_fields=["estado", "respeta_politica_fuente", "requiere_revision_manual"])

    extractor.habilitado = True
    extractor.solo_preview = True
    extractor.max_paginas = 1
    extractor.max_productos = 10
    extractor.delay_segundos = Decimal("2.00")
    extractor.save(update_fields=["habilitado", "solo_preview", "max_paginas", "max_productos", "delay_segundos"])
    return extractor


def reparar_extractor_gangahome():
    fuente = (
        FuenteWeb.objects.filter(Q(nombre__iexact="Ganga Home") | Q(url_base__icontains="gangahome.com.ar"))
        .order_by("id")
        .first()
    )
    if not fuente:
        fuente = FuenteWeb.objects.create(
            nombre="Ganga Home",
            url_base=GANGAHOME_URL_BASE,
            tipo_fuente="tienda_online",
            rubro_principal="hogar/deco",
            activa=True,
            pais="Argentina",
            moneda_principal="ARS",
        )
    fuente.url_base = GANGAHOME_URL_BASE
    fuente.activa = True
    fuente.save(update_fields=["url_base", "activa", "fecha_actualizacion"])

    conector = fuente.conectores.filter(tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO).first()
    if not conector:
        conector = ConectorFuente.objects.create(
            fuente_web=fuente,
            nombre="Ganga Home - Conector web controlado",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_BORRADOR,
            requiere_revision_manual=True,
            respeta_politica_fuente=False,
        )

    extractor, _ = ConfiguracionExtractorWeb.objects.get_or_create(
        conector=conector,
        defaults={
            "url_inicio": GANGAHOME_URL_BASE,
            "url_categoria": GANGAHOME_URL_CATEGORIA,
            "pagina_prueba_url": GANGAHOME_URL_CATEGORIA,
            "dominio_permitido": GANGAHOME_DOMINIO,
            "modo_extraccion": ConfiguracionExtractorWeb.MODO_MIXTO,
            "solo_preview": True,
        },
    )
    extractor.url_inicio = GANGAHOME_URL_BASE
    extractor.url_categoria = GANGAHOME_URL_CATEGORIA
    extractor.pagina_prueba_url = GANGAHOME_URL_CATEGORIA
    extractor.dominio_permitido = normalizar_dominio(GANGAHOME_DOMINIO)
    extractor.habilitado = True
    extractor.solo_preview = True
    extractor.max_paginas = 1
    extractor.max_productos = 10
    extractor.delay_segundos = Decimal("2.00")
    extractor.save(
        update_fields=[
            "url_inicio",
            "url_categoria",
            "pagina_prueba_url",
            "dominio_permitido",
            "habilitado",
            "solo_preview",
            "max_paginas",
            "max_productos",
            "delay_segundos",
            "fecha_actualizacion",
        ]
    )
    habilitar_extractor_preview_controlado(extractor)
    return fuente, conector, extractor
