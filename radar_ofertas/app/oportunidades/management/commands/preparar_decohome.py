import os

from django.core.management.base import BaseCommand

from oportunidades.models import ConectorFuente, FuenteWeb, PoliticaExtraccionFuente


def preparar_decohome():
    url_base = os.getenv("DECOHOME_URL_BASE", "https://www.decohome.com.ar/")
    fuente, _ = FuenteWeb.objects.update_or_create(
        nombre="Deco Home",
        defaults={
            "url_base": url_base,
            "tipo_fuente": FuenteWeb.TIPO_TIENDA_ONLINE,
            "rubro_principal": "deco/hogar/bazar",
            "activa": True,
            "prioridad": 1,
            "pais": "Argentina",
            "moneda_principal": "ARS",
            "descripcion": "Fuente candidata para radar multifuente. Requiere auditoria antes de cualquier automatizacion.",
        },
    )
    PoliticaExtraccionFuente.objects.update_or_create(
        fuente=fuente,
        defaults={
            "semaforo": PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
            "metodo_preferido": PoliticaExtraccionFuente.METODO_PENDIENTE_REVISION,
            "permite_scraping": False,
            "requiere_login": False,
            "tiene_captcha": False,
            "tiene_api": False,
            "tiene_afiliados": False,
            "robots_txt_revisado": False,
            "terminos_revisados": False,
            "riesgo_tecnico": PoliticaExtraccionFuente.RIESGO_DESCONOCIDO,
            "riesgo_legal": PoliticaExtraccionFuente.RIESGO_DESCONOCIDO,
            "observaciones": (
                "Pendiente de auditoria. No automatizar hasta revisar robots.txt, terminos y disponibilidad "
                "de catalogos o recursos permitidos."
            ),
        },
    )
    conector, _ = ConectorFuente.objects.update_or_create(
        fuente_web=fuente,
        nombre="Deco Home - Conector web pendiente de auditoria",
        defaults={
            "tipo_conector": ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            "estado": ConectorFuente.ESTADO_BORRADOR,
            "requiere_revision_manual": True,
            "respeta_politica_fuente": False,
            "descripcion": (
                "Conector preparado como borrador. No ejecutar scraping hasta que la fuente sea auditada "
                "y el semaforo lo permita."
            ),
        },
    )
    return fuente, conector


class Command(BaseCommand):
    help = "Prepara FuenteWeb, politica y conector borrador para Deco Home."

    def handle(self, *args, **options):
        fuente, conector = preparar_decohome()
        self.stdout.write(self.style.SUCCESS("Deco Home preparada."))
        self.stdout.write(f"Fuente ID: {fuente.pk}")
        self.stdout.write(f"Conector ID: {conector.pk}")
