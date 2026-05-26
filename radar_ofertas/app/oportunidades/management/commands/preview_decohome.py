from django.core.management.base import BaseCommand

from oportunidades.management.commands.configurar_extractor_decohome import configurar_extractor_decohome
from oportunidades.models import ConfiguracionExtractorWeb
from oportunidades.services.extractor_web_service import obtener_condiciones_faltantes_extractor
from oportunidades.services.selector_preview_service import probar_url_preview


class Command(BaseCommand):
    help = "Ejecuta preview de Deco Home si la politica lo permite."

    def handle(self, *args, **options):
        config, _ = configurar_extractor_decohome()
        faltantes = obtener_condiciones_faltantes_extractor(config.conector)
        if faltantes:
            self.stdout.write(self.style.WARNING("Preview bloqueado. Falta: " + ", ".join(faltantes)))
            return
        if config.modo_extraccion == ConfiguracionExtractorWeb.MODO_PREVIEW_MANUAL:
            self.stdout.write(
                self.style.WARNING(
                    "Faltan selectores o configuracion JSON-LD. Usar /extractores/<id>/selectores/ o configurar_selectores_decohome."
                )
            )
            return
        resultado = probar_url_preview(config)
        self.stdout.write(f"Status: {'OK' if resultado['ok'] else 'NO OK'}")
        self.stdout.write(f"Productos detectados: {resultado['productos_detectados']}")
        self.stdout.write(f"Errores: {len(resultado['errores'])}")
        self.stdout.write(f"Requiere JS probable: {resultado.get('diagnostico', {}).get('requiere_js_probable')}")
        if config.ultimo_preview_mensaje:
            self.stdout.write(f"Mensaje: {config.ultimo_preview_mensaje}")
