from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import FuenteWeb, LoteCaptura
from oportunidades.services.lotes_captura_service import crear_lote_captura


class Command(BaseCommand):
    help = "Crea un lote manual para registrar cargas controladas."

    def add_arguments(self, parser):
        parser.add_argument("--fuente-id", type=int)
        parser.add_argument("--nombre", required=True)
        parser.add_argument("--tipo-carga", choices=[v for v, _ in LoteCaptura.TIPO_CARGA_CHOICES], default="piloto")
        parser.add_argument("--observaciones")

    def handle(self, *args, **options):
        fuente = None
        if options["fuente_id"]:
            try:
                fuente = FuenteWeb.objects.get(pk=options["fuente_id"])
            except FuenteWeb.DoesNotExist as exc:
                raise CommandError("La fuente indicada no existe.") from exc
        lote = crear_lote_captura(
            origen="manual", fuente_web=fuente, nombre=options["nombre"],
            tipo_carga=options["tipo_carga"], observaciones=options["observaciones"], estado="creado",
        )
        self.stdout.write(self.style.SUCCESS(f"Lote manual creado: #{lote.id} {lote.nombre}"))
