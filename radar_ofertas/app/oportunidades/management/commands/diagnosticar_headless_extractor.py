from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import ConfiguracionExtractorWeb
from oportunidades.services.headless_diagnostic_service import comparar_html_requests_vs_headless, diagnosticar_requiere_headless


class Command(BaseCommand):
    help = "Diagnostica si un extractor podria requerir navegador headless opcional."

    def add_arguments(self, parser):
        parser.add_argument("--extractor-id", type=int, required=True)

    def handle(self, *args, **options):
        extractor = ConfiguracionExtractorWeb.objects.filter(pk=options["extractor_id"]).first()
        if not extractor:
            raise CommandError("Extractor no encontrado.")
        diagnostico = diagnosticar_requiere_headless(extractor)
        comparacion = comparar_html_requests_vs_headless(extractor)
        self.stdout.write(f"Headless habilitado: {diagnostico.get('habilitado')}")
        self.stdout.write(f"Provider: {diagnostico.get('provider')}")
        self.stdout.write(f"Estado comparacion: {comparacion.get('estado')}")
        self.stdout.write(f"Requests OK: {comparacion.get('requests_ok')}")
        self.stdout.write(f"Headless OK: {comparacion.get('headless_ok')}")
        self.stdout.write(f"Mensaje: {comparacion.get('mensaje')}")
