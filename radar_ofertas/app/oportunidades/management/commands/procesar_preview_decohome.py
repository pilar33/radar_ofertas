from django.core.management.base import BaseCommand

from oportunidades.management.commands.preparar_decohome import preparar_decohome
from oportunidades.models import ConfiguracionExtractorWeb
from oportunidades.services.procesamiento_preview_service import procesar_resultados_seleccionados


class Command(BaseCommand):
    help = "Procesa resultados seleccionados del ultimo preview de Deco Home."

    def add_arguments(self, parser):
        parser.add_argument("--max", type=int, default=10)

    def handle(self, *args, **options):
        fuente, _ = preparar_decohome()
        extractor = ConfiguracionExtractorWeb.objects.filter(conector__fuente_web=fuente).first()
        if not extractor:
            self.stdout.write(self.style.WARNING("No hay extractor Deco Home configurado."))
            return
        ejecucion = extractor.conector.ejecuciones.first()
        if not ejecucion:
            self.stdout.write(self.style.WARNING("No hay preview ejecutado."))
            return
        if not ejecucion.resultados_web.filter(seleccionado=True).exists():
            self.stdout.write("No hay resultados seleccionados. Seleccionar desde la vista de resultados.")
            return
        resumen = procesar_resultados_seleccionados(ejecucion, limite=options["max"])
        self.stdout.write(self.style.SUCCESS("Procesamiento finalizado."))
        self.stdout.write(str(resumen))
