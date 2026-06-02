from pathlib import Path

from django.core.management.base import BaseCommand

from oportunidades.services.dataset_export_service import exportar_historial_precios_csv


class Command(BaseCommand):
    help = "Exporta historial de precios a CSV."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="data/exports/historial_precios.csv")

    def handle(self, *args, **options):
        path = Path(options["output"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as archivo:
            exportar_historial_precios_csv(output=archivo)
        self.stdout.write(self.style.SUCCESS(f"Historial exportado: {path}"))
