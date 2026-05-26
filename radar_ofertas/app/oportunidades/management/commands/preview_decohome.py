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
            politica = getattr(config.conector.fuente_web, "politica_extraccion", None)
            if politica:
                self.stdout.write(f"semaforo={politica.semaforo}")
                self.stdout.write(f"permite_scraping={politica.permite_scraping}")
                self.stdout.write(f"robots_txt_revisado={politica.robots_txt_revisado}")
                self.stdout.write(f"terminos_revisados={politica.terminos_revisados}")
                self.stdout.write(f"requiere_login={politica.requiere_login}")
                self.stdout.write(f"tiene_captcha={politica.tiene_captcha}")
            self.stdout.write(f"conector_activo={config.conector.estado == 'activo'}")
            self.stdout.write(f"extractor_habilitado={config.habilitado}")
            self.stdout.write(f"selectores_configurados={bool(config.product_card_selector or config.modo_extraccion == ConfiguracionExtractorWeb.MODO_JSON_LD)}")
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
