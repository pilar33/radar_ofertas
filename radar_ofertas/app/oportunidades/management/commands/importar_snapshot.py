from django.core.management.base import BaseCommand, CommandError

from oportunidades.services.backup_service import importar_snapshot_json


class Command(BaseCommand):
    help = "Importa snapshot JSON de datos clave."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            resumen = importar_snapshot_json(options["input"], dry_run=options["dry_run"])
        except FileNotFoundError as exc:
            raise CommandError(f"No existe el archivo: {options['input']}") from exc
        self.stdout.write(str(resumen))
