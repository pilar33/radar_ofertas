from urllib.parse import urlparse

from django.core.management.base import BaseCommand

from oportunidades.management.commands.configurar_extractor_decohome import configurar_extractor_decohome
from oportunidades.models import ConfiguracionExtractorWeb
from oportunidades.services.extractor_web_service import obtener_condiciones_faltantes_extractor


class Command(BaseCommand):
    help = "Configura pagina de prueba y selectores de Deco Home sin inventar selectores."

    def add_arguments(self, parser):
        parser.add_argument("--pagina-prueba", default="")
        parser.add_argument("--product-card-selector", default="")
        parser.add_argument("--title-selector", default="")
        parser.add_argument("--price-selector", default="")
        parser.add_argument("--url-selector", default="")
        parser.add_argument("--image-selector", default="")
        parser.add_argument("--modo", choices=[c[0] for c in ConfiguracionExtractorWeb.MODO_CHOICES], default="")
        parser.add_argument("--habilitar-preview", action="store_true")

    def handle(self, *args, **options):
        config, _ = configurar_extractor_decohome()
        if options["pagina_prueba"]:
            config.pagina_prueba_url = options["pagina_prueba"]
            config.dominio_permitido = urlparse(options["pagina_prueba"]).netloc or config.dominio_permitido
        if options["modo"]:
            config.modo_extraccion = options["modo"]
        for opt, field in [
            ("product_card_selector", "product_card_selector"),
            ("title_selector", "title_selector"),
            ("price_selector", "price_selector"),
            ("url_selector", "url_selector"),
            ("image_selector", "image_selector"),
        ]:
            if options[opt]:
                setattr(config, field, options[opt])
        if options["habilitar_preview"]:
            config.habilitado = True
            faltantes = obtener_condiciones_faltantes_extractor(config.conector)
            if faltantes:
                config.habilitado = False
                self.stdout.write(self.style.WARNING("No se puede habilitar preview. Falta: " + ", ".join(faltantes)))
        config.save()
        self.stdout.write(self.style.SUCCESS("Selectores Deco Home actualizados."))
        self.stdout.write(f"Extractor ID: {config.pk}")
        self.stdout.write(f"Modo: {config.modo_extraccion}")
        self.stdout.write(f"Pagina prueba: {config.pagina_prueba_url or '-'}")
        self.stdout.write(f"Habilitado: {'Si' if config.habilitado else 'No'}")
