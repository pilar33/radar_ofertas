from oportunidades.models import ConectorFuente, FuenteWeb, PoliticaExtraccionFuente


def crear_fuente_wizard(datos):
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
    return fuente, conector, creada, conector_creado
