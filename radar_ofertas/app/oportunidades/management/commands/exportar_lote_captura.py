from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import LoteCaptura
from oportunidades.services.dataset_export_service import exportar_lote_captura_csv


class Command(BaseCommand):
    help = "Exporta un lote de captura a CSV."

    def add_arguments(self, parser):
        parser.add_argument("--lote-id", type=int, required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        try:
            lote = LoteCaptura.objects.get(pk=options["lote_id"])
        except LoteCaptura.DoesNotExist as exc:
            raise CommandError("El lote indicado no existe.") from exc
        destino = Path(options["output"])
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(exportar_lote_captura_csv(lote).getvalue(), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Lote #{lote.id} exportado a {destino}"))
