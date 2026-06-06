from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone

from oportunidades.services.backup_service import exportar_snapshot_json
from oportunidades.services.dataset_export_service import (
    exportar_dataset_completo_zip,
    exportar_dataset_productos_csv,
    exportar_historial_precios_csv,
)


class Command(BaseCommand):
    help = "Genera snapshot JSON, CSVs y ZIP del dataset en una carpeta local."

    def add_arguments(self, parser):
        parser.add_argument("--base-dir", default="data", help="Carpeta base para backups y exports.")

    def handle(self, *args, **options):
        base_dir = Path(options["base_dir"])
        backups_dir = base_dir / "backups"
        exports_dir = base_dir / "exports"
        backups_dir.mkdir(parents=True, exist_ok=True)
        exports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = backups_dir / f"snapshot_radar_{timestamp}.json"
        productos_path = exports_dir / f"productos_dataset_{timestamp}.csv"
        historial_path = exports_dir / f"historial_precios_{timestamp}.csv"
        zip_path = exports_dir / f"radar_dataset_{timestamp}.zip"

        snapshot_path.write_text(exportar_snapshot_json(), encoding="utf-8")
        productos_path.write_text(exportar_dataset_productos_csv().getvalue(), encoding="utf-8")
        historial_path.write_text(exportar_historial_precios_csv().getvalue(), encoding="utf-8")
        zip_path.write_bytes(exportar_dataset_completo_zip().getvalue())

        self.stdout.write(self.style.SUCCESS("Backup rapido generado."))
        self.stdout.write(f"Snapshot JSON: {snapshot_path}")
        self.stdout.write(f"Productos CSV: {productos_path}")
        self.stdout.write(f"Historial CSV: {historial_path}")
        self.stdout.write(f"Dataset ZIP: {zip_path}")
