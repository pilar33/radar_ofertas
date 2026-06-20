from django.core.management.base import BaseCommand

from oportunidades.models import LoteCaptura
from oportunidades.services.lotes_captura_service import recalcular_contadores_lote


class Command(BaseCommand):
    help = "Recalcula contadores y calidad de todos los lotes de captura."

    def handle(self, *args, **options):
        total = 0
        for lote in LoteCaptura.objects.iterator():
            recalcular_contadores_lote(lote)
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Lotes recalculados: {total}"))
