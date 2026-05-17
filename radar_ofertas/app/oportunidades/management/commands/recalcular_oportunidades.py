from django.core.management.base import BaseCommand

from oportunidades.models import Oportunidad
from oportunidades.services.clasificacion_service import clasificar_oportunidad


class Command(BaseCommand):
    help = "Recalcula margen, riesgo, puntaje y clasificacion de todas las oportunidades."

    def handle(self, *args, **options):
        conteos = {
            "procesadas": 0,
            "reventa": 0,
            "afiliado": 0,
            "descartar": 0,
        }

        oportunidades = Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente")

        for oportunidad in oportunidades.iterator():
            evaluacion = clasificar_oportunidad(
                oportunidad.producto,
                oportunidad.precio_actual,
                precio_reventa_estimado=oportunidad.precio_reventa_estimado or None,
            )
            oportunidad.precio_reventa_estimado = evaluacion["precio_reventa_estimado"]
            oportunidad.margen_estimado = evaluacion["margen_estimado"]
            oportunidad.porcentaje_margen = evaluacion["porcentaje_margen"]
            oportunidad.tipo = evaluacion["tipo"]
            oportunidad.riesgo = evaluacion["riesgo"]
            oportunidad.puntaje = evaluacion["puntaje"]
            oportunidad.motivo = evaluacion["motivo"]
            oportunidad.save(
                update_fields=[
                    "precio_reventa_estimado",
                    "margen_estimado",
                    "porcentaje_margen",
                    "tipo",
                    "riesgo",
                    "puntaje",
                    "motivo",
                ]
            )

            conteos["procesadas"] += 1
            conteos[evaluacion["tipo"]] += 1

        self.stdout.write(self.style.SUCCESS(f"Oportunidades procesadas: {conteos['procesadas']}"))
        self.stdout.write(f"Reventa: {conteos['reventa']}")
        self.stdout.write(f"Afiliado: {conteos['afiliado']}")
        self.stdout.write(f"Descartar: {conteos['descartar']}")
