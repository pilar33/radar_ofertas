from pathlib import Path

from django.core.management.base import BaseCommand

from oportunidades.services.dataset_export_service import exportar_dataset_completo_zip


class Command(BaseCommand):
    help = "Exporta dataset completo a ZIP."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="data/exports/radar_dataset.zip")

    def handle(self, *args, **options):
        path = Path(options["output"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(exportar_dataset_completo_zip().getvalue())
        self.stdout.write(self.style.SUCCESS(f"Dataset completo exportado: {path}"))
