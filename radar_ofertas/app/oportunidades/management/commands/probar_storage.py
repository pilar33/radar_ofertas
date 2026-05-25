from django.core.management.base import BaseCommand

from oportunidades.services.storage_service import probar_storage


class Command(BaseCommand):
    help = "Prueba escritura, lectura y eliminacion en default_storage."

    def add_arguments(self, parser):
        parser.add_argument("--keep", action="store_true", help="Conserva el archivo de prueba para revision manual.")

    def handle(self, *args, **options):
        resultado = probar_storage(keep=options["keep"])
        if resultado["ok"]:
            self.stdout.write(self.style.SUCCESS(resultado["mensaje"]))
            if resultado.get("path"):
                self.stdout.write(f"Path: {resultado['path']}")
        else:
            self.stdout.write(self.style.ERROR(resultado["mensaje"]))
