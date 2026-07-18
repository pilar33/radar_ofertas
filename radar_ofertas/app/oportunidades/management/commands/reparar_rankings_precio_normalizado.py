from django.core.management.base import BaseCommand

from oportunidades.models import LoteRanking
from oportunidades.services.ranking_import_service import reparar_precios_normalizados_lote


class Command(BaseCommand):
    help = "Recalcula precios normalizados de rankings ya importados desde texto_original."

    def add_arguments(self, parser):
        parser.add_argument("--lote-id", type=int, default=None)

    def handle(self, *args, **options):
        qs = LoteRanking.objects.all()
        if options["lote_id"]:
            qs = qs.filter(pk=options["lote_id"])
        total = 0
        for lote in qs:
            resumen = reparar_precios_normalizados_lote(lote)
            total += resumen["actualizados"]
            self.stdout.write(f"Lote {lote.id}: {resumen['actualizados']} items. {resumen['mensaje']}")
        self.stdout.write(self.style.SUCCESS(f"Items actualizados: {total}."))
