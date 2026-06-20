from django.core.management.base import BaseCommand

from oportunidades.models import LoteCaptura


class Command(BaseCommand):
    help = "Lista lotes de captura con filtros operativos."

    def add_arguments(self, parser):
        parser.add_argument("--fuente-id", type=int)
        parser.add_argument("--origen")
        parser.add_argument("--estado")
        parser.add_argument("--limite", type=int, default=20)

    def handle(self, *args, **options):
        lotes = LoteCaptura.objects.select_related("fuente_web").all()
        for campo in ("fuente_id", "origen", "estado"):
            valor = options.get(campo)
            if valor:
                lotes = lotes.filter(**{campo: valor})
        for lote in lotes[: options["limite"]]:
            self.stdout.write(
                f"#{lote.id} | {lote.fecha_inicio:%Y-%m-%d %H:%M} | {lote.nombre} | "
                f"{lote.estado} | detectados={lote.productos_detectados} procesados={lote.productos_procesados}"
            )
        self.stdout.write(self.style.SUCCESS(f"Lotes mostrados: {min(lotes.count(), options['limite'])}"))
