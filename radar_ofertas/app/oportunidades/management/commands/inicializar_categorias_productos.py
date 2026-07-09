from django.core.management.base import BaseCommand

from oportunidades.services.categorias_service import asegurar_categorias_base


class Command(BaseCommand):
    help = "Crea o completa las categorias normalizadas base del Radar."

    def handle(self, *args, **options):
        resumen = asegurar_categorias_base()
        self.stdout.write(
            self.style.SUCCESS(
                f"Categorias base listas. Creadas: {resumen['creadas']}. Actualizadas: {resumen['actualizadas']}."
            )
        )
