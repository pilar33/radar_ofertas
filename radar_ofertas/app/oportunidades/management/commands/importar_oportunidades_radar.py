from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from oportunidades.services.radar_oportunidades_service import importar_oportunidades_desde_texto
from oportunidades.services.radar_texto_parser_service import parsear_texto_radar


class Command(BaseCommand):
    help = "Importa oportunidades Radar desde un archivo de texto pegado/exportado."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True)
        parser.add_argument("--origen", default="chatgpt_radar")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--importar", action="store_true")
        parser.add_argument("--min-score", type=int, default=None)

    def handle(self, *args, **options):
        path = Path(options["input"])
        if not path.exists():
            raise CommandError(f"No existe el archivo: {path}")
        texto = path.read_text(encoding="utf-8")
        oportunidades = parsear_texto_radar(texto)
        self.stdout.write(f"Oportunidades detectadas: {len(oportunidades)}")
        for oportunidad in oportunidades:
            self.stdout.write(
                f"- {oportunidad.get('tienda') or '-'} | {oportunidad.get('producto_nombre')} | "
                f"precio={oportunidad.get('precio_actual') or '-'} | score={oportunidad.get('score_radar')}"
            )
        if options["dry_run"] or not options["importar"]:
            self.stdout.write("Dry-run: no se guardaron oportunidades.")
            return
        importacion, creadas, _ = importar_oportunidades_desde_texto(
            texto,
            origen=options["origen"],
            confirmar=True,
            min_score=options["min_score"],
        )
        self.stdout.write(self.style.SUCCESS(f"Importacion #{importacion.pk}: creadas={len(creadas)}."))
