from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import FuenteWeb
from oportunidades.services.estado_fuente_service import evaluar_estado_operativo_fuente


class Command(BaseCommand):
    help = "Muestra el estado operativo de una fuente."

    def add_arguments(self, parser):
        parser.add_argument("--fuente-id", type=int, required=True)

    def handle(self, *args, **options):
        fuente = FuenteWeb.objects.filter(pk=options["fuente_id"]).first()
        if not fuente:
            raise CommandError("Fuente no encontrada.")
        estado = evaluar_estado_operativo_fuente(fuente)
        self.stdout.write(f"Fuente: {fuente.nombre}")
        self.stdout.write(f"Estado: {estado['estado']}")
        self.stdout.write(f"Puede preview: {estado['puede_preview']}")
        self.stdout.write(f"Puede procesar: {estado['puede_procesar']}")
        self.stdout.write(f"Requiere JS: {estado['requiere_js']}")
        self.stdout.write("Faltantes: " + (", ".join(estado["faltantes"]) or "-"))
        self.stdout.write("Recomendacion: " + estado["recomendacion"])
