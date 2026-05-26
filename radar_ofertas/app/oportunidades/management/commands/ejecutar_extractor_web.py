from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import ConectorFuente
from oportunidades.services.extractor_web_service import extraer_productos_preview


class Command(BaseCommand):
    help = "Ejecuta extractor web controlado en modo preview o procesamiento."

    def add_arguments(self, parser):
        parser.add_argument("--conector-id", type=int, required=True)
        parser.add_argument("--procesar", action="store_true")
        parser.add_argument("--max-productos", type=int, required=False)
        parser.add_argument("--max-paginas", type=int, required=False)

    def handle(self, *args, **options):
        try:
            conector = ConectorFuente.objects.get(pk=options["conector_id"])
        except ConectorFuente.DoesNotExist as exc:
            raise CommandError("Conector no encontrado.") from exc
        ejecucion = extraer_productos_preview(
            conector,
            procesar=options["procesar"],
            max_productos=options.get("max_productos"),
            max_paginas=options.get("max_paginas"),
        )
        self.stdout.write(f"Status: {ejecucion.estado}")
        self.stdout.write(f"Productos detectados: {ejecucion.productos_detectados}")
        self.stdout.write(f"Procesados: {ejecucion.productos_creados}")
        self.stdout.write(f"Errores: {ejecucion.errores}")
        if ejecucion.mensaje:
            self.stdout.write(f"Mensaje: {ejecucion.mensaje}")
