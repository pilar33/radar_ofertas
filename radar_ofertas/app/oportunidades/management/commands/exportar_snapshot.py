from pathlib import Path

from django.core.management.base import BaseCommand

from oportunidades.services.backup_service import exportar_snapshot_json


class Command(BaseCommand):
    help = "Exporta snapshot JSON de datos clave."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="data/backups/snapshot_radar.json")

    def handle(self, *args, **options):
        path = Path(options["output"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(exportar_snapshot_json(), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Snapshot exportado: {path}"))
