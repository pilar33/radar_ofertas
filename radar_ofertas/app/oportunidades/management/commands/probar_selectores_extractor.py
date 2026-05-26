from django.core.management.base import BaseCommand

from oportunidades.models import ConfiguracionExtractorWeb
from oportunidades.services.selector_preview_service import probar_url_preview


class Command(BaseCommand):
    help = "Prueba selectores de un extractor contra una URL concreta sin procesar productos."

    def add_arguments(self, parser):
        parser.add_argument("--extractor-id", type=int, required=True)

    def handle(self, *args, **options):
        config = ConfiguracionExtractorWeb.objects.get(pk=options["extractor_id"])
        resultado = probar_url_preview(config)
        self.stdout.write(f"Status: {'OK' if resultado['ok'] else 'NO OK'}")
        self.stdout.write(f"Productos detectados: {resultado['productos_detectados']}")
        self.stdout.write(f"Requiere JS probable: {resultado.get('diagnostico', {}).get('requiere_js_probable')}")
        self.stdout.write(f"Tiene JSON-LD: {resultado.get('diagnostico', {}).get('tiene_json_ld')}")
        self.stdout.write(f"Tiene productos HTML probable: {resultado.get('diagnostico', {}).get('tiene_productos_html_probable')}")
        if resultado["errores"]:
            self.stdout.write("Errores: " + " | ".join(resultado["errores"]))
        for muestra in resultado["muestras"][:5]:
            self.stdout.write(f"- {muestra.get('titulo') or '-'} | {muestra.get('precio_texto') or '-'}")
