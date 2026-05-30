from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import ConfiguracionExtractorWeb, FuenteWeb
from oportunidades.services.estado_fuente_service import evaluar_estado_operativo_fuente
from oportunidades.services.selector_preview_service import probar_url_preview


class Command(BaseCommand):
    help = "Ejecuta preview controlado para una fuente si la politica lo permite."

    def add_arguments(self, parser):
        parser.add_argument("--fuente-id", type=int, required=True)

    def handle(self, *args, **options):
        fuente = FuenteWeb.objects.filter(pk=options["fuente_id"]).first()
        if not fuente:
            raise CommandError("Fuente no encontrada.")
        estado = evaluar_estado_operativo_fuente(fuente)
        if not estado["puede_preview"]:
            self.stdout.write(self.style.WARNING("Preview bloqueado."))
            self.stdout.write("Faltantes: " + ", ".join(estado["faltantes"]))
            return
        extractor = ConfiguracionExtractorWeb.objects.filter(conector=estado["conector"]).first()
        if not extractor:
            self.stdout.write(self.style.WARNING("No hay extractor configurado."))
            return
        resultado = probar_url_preview(extractor)
        self.stdout.write(f"Status: {'OK' if resultado['ok'] else 'NO OK'}")
        self.stdout.write(f"Productos detectados: {resultado['productos_detectados']}")
        self.stdout.write(f"Errores: {len(resultado['errores'])}")
