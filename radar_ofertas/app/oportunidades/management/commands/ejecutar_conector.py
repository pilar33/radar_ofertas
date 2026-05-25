from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import ConectorFuente
from oportunidades.services.conector_catalogo_service import ejecutar_conector_catalogo


class Command(BaseCommand):
    help = "Ejecuta un conector CSV/Excel permitido."

    def add_arguments(self, parser):
        parser.add_argument("--conector-id", type=int, required=True)

    def handle(self, *args, **options):
        try:
            conector = ConectorFuente.objects.get(pk=options["conector_id"])
        except ConectorFuente.DoesNotExist as exc:
            raise CommandError("Conector no encontrado.") from exc

        ejecucion = ejecutar_conector_catalogo(conector)
        self.stdout.write(f"Estado: {ejecucion.estado}")
        self.stdout.write(f"Productos detectados: {ejecucion.productos_detectados}")
        self.stdout.write(f"Productos creados: {ejecucion.productos_creados}")
        self.stdout.write(f"Productos actualizados: {ejecucion.productos_actualizados}")
        self.stdout.write(f"Precios creados: {ejecucion.precios_creados}")
        self.stdout.write(f"Errores: {ejecucion.errores}")
        if ejecucion.mensaje:
            self.stdout.write(f"Mensaje: {ejecucion.mensaje}")
