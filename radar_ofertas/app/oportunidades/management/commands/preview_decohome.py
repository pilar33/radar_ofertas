from django.core.management.base import BaseCommand

from oportunidades.management.commands.configurar_extractor_decohome import configurar_extractor_decohome
from oportunidades.services.extractor_web_service import extraer_productos_preview


class Command(BaseCommand):
    help = "Ejecuta preview de Deco Home si la politica lo permite."

    def handle(self, *args, **options):
        config, _ = configurar_extractor_decohome()
        ejecucion = extraer_productos_preview(config.conector, procesar=False)
        self.stdout.write(f"Status: {ejecucion.estado}")
        self.stdout.write(f"Productos detectados: {ejecucion.productos_detectados}")
        self.stdout.write(f"Errores: {ejecucion.errores}")
        if ejecucion.mensaje:
            self.stdout.write(f"Mensaje: {ejecucion.mensaje}")
