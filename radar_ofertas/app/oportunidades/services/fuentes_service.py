from django.utils import timezone

from oportunidades.models import FuenteWeb, PoliticaExtraccionFuente


def registrar_fuente_web(nombre, url_base, tipo_fuente, politica=None, **kwargs):
    fuente, _ = FuenteWeb.objects.update_or_create(
        nombre=nombre,
        defaults={
            "url_base": url_base,
            "tipo_fuente": tipo_fuente,
            **kwargs,
        },
    )
    if politica:
        PoliticaExtraccionFuente.objects.update_or_create(
            fuente=fuente,
            defaults={**politica, "fecha_revision": politica.get("fecha_revision") or timezone.now()},
        )
    return fuente


def clasificar_fuente_por_politica(fuente):
    politica = getattr(fuente, "politica_extraccion", None)
    if not politica:
        return PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO
    return politica.semaforo


def obtener_fuentes_verdes():
    return FuenteWeb.objects.filter(politica_extraccion__semaforo=PoliticaExtraccionFuente.SEMAFORO_VERDE)


def obtener_fuentes_amarillas():
    return FuenteWeb.objects.filter(politica_extraccion__semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO)


def obtener_fuentes_rojas():
    return FuenteWeb.objects.filter(politica_extraccion__semaforo=PoliticaExtraccionFuente.SEMAFORO_ROJO)


def fuente_permite_automatizacion(fuente):
    politica = getattr(fuente, "politica_extraccion", None)
    if not politica:
        return False
    if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_ROJO:
        return False
    if politica.metodo_preferido == PoliticaExtraccionFuente.METODO_NO_PERMITIDO:
        return False
    return politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_VERDE or politica.permite_scraping or politica.tiene_api
