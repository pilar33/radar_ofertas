from django.core.management.base import BaseCommand

from oportunidades.models import OportunidadRadar
from oportunidades.services.radar_oportunidades_service import recalcular_oportunidad_radar


class Command(BaseCommand):
    help = "Recalcula score y nivel de oportunidades Radar."

    def handle(self, *args, **options):
        total = 0
        for oportunidad in OportunidadRadar.objects.all():
            recalcular_oportunidad_radar(oportunidad)
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Oportunidades Radar recalculadas: {total}"))
