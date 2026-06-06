from django.core.management.base import BaseCommand

from oportunidades.services.ranking_comercial_service import recalcular_ranking_comercial


class Command(BaseCommand):
    help = "Recalcula score comercial de ProductoFuente."

    def add_arguments(self, parser):
        parser.add_argument("--fuente-id", type=int)
        parser.add_argument("--producto-fuente-id", type=int)
        parser.add_argument("--solo-revisados", action="store_true")
        parser.add_argument("--limite", type=int)

    def handle(self, *args, **options):
        resultados = recalcular_ranking_comercial(
            fuente_id=options.get("fuente_id"),
            producto_fuente_id=options.get("producto_fuente_id"),
            solo_revisados=options.get("solo_revisados"),
            limite=options.get("limite"),
        )
        self.stdout.write(self.style.SUCCESS(f"Ranking recalculado. Productos: {len(resultados)}"))
