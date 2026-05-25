from django.core.management.base import BaseCommand

from oportunidades.services.storage_service import probar_storage


class Command(BaseCommand):
    help = "Prueba escritura, lectura y eliminacion en default_storage."

    def handle(self, *args, **options):
        resultado = probar_storage()
        if resultado["ok"]:
            self.stdout.write(self.style.SUCCESS(resultado["mensaje"]))
        else:
            self.stdout.write(self.style.ERROR(resultado["mensaje"]))
