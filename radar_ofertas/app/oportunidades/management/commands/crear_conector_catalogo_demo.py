from django.core.management.base import BaseCommand

from oportunidades.models import ConectorFuente, FuenteWeb, PoliticaExtraccionFuente


class Command(BaseCommand):
    help = "Crea fuente y conector demo de catalogo CSV/Excel sin scraping."

    def handle(self, *args, **options):
        fuente, _ = FuenteWeb.objects.update_or_create(
            nombre="Catalogo Demo Mayorista",
            defaults={
                "url_base": "https://example.com/",
                "tipo_fuente": FuenteWeb.TIPO_EXCEL_CSV,
                "rubro_principal": "demo",
                "activa": True,
                "descripcion": "Fuente demo para probar conector CSV/Excel sin scraping.",
            },
        )
        PoliticaExtraccionFuente.objects.update_or_create(
            fuente=fuente,
            defaults={
                "semaforo": PoliticaExtraccionFuente.SEMAFORO_VERDE,
                "metodo_preferido": PoliticaExtraccionFuente.METODO_CSV_EXCEL,
                "permite_scraping": False,
                "requiere_login": False,
                "tiene_captcha": False,
                "tiene_api": False,
                "tiene_afiliados": False,
                "riesgo_tecnico": PoliticaExtraccionFuente.RIESGO_BAJO,
                "riesgo_legal": PoliticaExtraccionFuente.RIESGO_BAJO,
                "observaciones": "Fuente demo para probar conector CSV/Excel sin scraping.",
            },
        )
        conector, creado = ConectorFuente.objects.update_or_create(
            fuente_web=fuente,
            nombre="Conector CSV Demo",
            defaults={
                "tipo_conector": ConectorFuente.TIPO_CSV_MANUAL,
                "estado": ConectorFuente.ESTADO_ACTIVO,
                "fuente_autorizo_uso": True,
                "requiere_descarga": False,
                "formato_recurso": ConectorFuente.FORMATO_CSV,
                "descripcion": "Conector demo para procesar archivos CSV cargados manualmente.",
            },
        )
        self.stdout.write(self.style.SUCCESS("Conector catalogo demo listo."))
        self.stdout.write(f"Conector ID: {conector.pk}")
        self.stdout.write(f"Creado: {'Si' if creado else 'No'}")
