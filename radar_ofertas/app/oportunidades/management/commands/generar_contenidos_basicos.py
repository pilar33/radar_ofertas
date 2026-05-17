from django.core.management.base import BaseCommand

from oportunidades.models import ContenidoSugerido, Oportunidad
from oportunidades.services.contenido_service import generar_contenido_basico


class Command(BaseCommand):
    help = "Genera contenido sugerido basico para oportunidades que todavia no tienen contenido."

    def handle(self, *args, **options):
        creados = 0
        oportunidades = (
            Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente")
            .filter(contenidos__isnull=True)
            .distinct()
        )

        for oportunidad in oportunidades.iterator():
            ContenidoSugerido.objects.create(
                oportunidad=oportunidad,
                generado_con_ia=False,
                **generar_contenido_basico(oportunidad),
            )
            creados += 1

        self.stdout.write(self.style.SUCCESS(f"Contenidos basicos creados: {creados}"))
