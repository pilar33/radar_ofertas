from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import FuenteWeb
from oportunidades.services.laboratorio_mapeo_service import (
    analizar_url_laboratorio,
    crear_sesion_laboratorio,
    guardar_laboratorio_como_extractor,
)


class Command(BaseCommand):
    help = "Analiza una URL y guarda la configuracion como extractor en modo preview."

    def add_arguments(self, parser):
        parser.add_argument("--url", required=True)
        parser.add_argument("--fuente-id", type=int, required=True)
        parser.add_argument("--limite", type=int, default=10)

    def handle(self, *args, **options):
        fuente = FuenteWeb.objects.filter(pk=options["fuente_id"]).first()
        if not fuente:
            raise CommandError("Fuente no encontrada.")
        resultado = analizar_url_laboratorio(options["url"], limite=options["limite"])
        sesion = crear_sesion_laboratorio(resultado, fuente_web=fuente)
        extractor = guardar_laboratorio_como_extractor(sesion, fuente_web=fuente)
        self.stdout.write(self.style.SUCCESS("Extractor guardado desde laboratorio."))
        self.stdout.write(f"Sesion ID: {sesion.pk}")
        self.stdout.write(f"Extractor ID: {extractor.pk}")
        self.stdout.write(f"Habilitado: {extractor.habilitado}")
        self.stdout.write(f"Productos detectados: {sesion.resultados.count()}")
