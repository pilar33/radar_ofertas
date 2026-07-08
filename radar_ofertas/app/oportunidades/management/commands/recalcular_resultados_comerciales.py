from django.core.management.base import BaseCommand

from oportunidades.models import CandidatoCompra
from oportunidades.services.seguimiento_comercial_service import recalcular_resultado_comercial


class Command(BaseCommand):
    help = "Recalcula resultados comerciales reales."

    def add_arguments(self, parser):
        parser.add_argument("--candidato-id", type=int)
        parser.add_argument("--producto-fuente-id", type=int)
        parser.add_argument("--limite", type=int, default=500)

    def handle(self, *args, **options):
        candidatos = CandidatoCompra.objects.all()
        if options["candidato_id"]:
            candidatos = candidatos.filter(pk=options["candidato_id"])
        if options["producto_fuente_id"]:
            candidatos = candidatos.filter(producto_fuente_id=options["producto_fuente_id"])
        total = 0
        for candidato in candidatos[: options["limite"]]:
            recalcular_resultado_comercial(candidato)
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Resultados comerciales recalculados: {total}"))
