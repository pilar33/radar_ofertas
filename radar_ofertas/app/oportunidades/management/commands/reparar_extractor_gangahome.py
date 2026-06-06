from django.core.management.base import BaseCommand

from oportunidades.services.preview_controlado_service import reparar_extractor_gangahome


class Command(BaseCommand):
    help = "Corrige y habilita el extractor de Ganga Home para preview controlado, sin procesar productos."

    def handle(self, *args, **options):
        fuente, conector, extractor = reparar_extractor_gangahome()
        self.stdout.write(self.style.SUCCESS("Extractor Ganga Home reparado para preview controlado."))
        self.stdout.write(f"Fuente ID: {fuente.pk}")
        self.stdout.write(f"Conector ID: {conector.pk}")
        self.stdout.write(f"Extractor ID: {extractor.pk}")
        self.stdout.write(f"url_inicio: {extractor.url_inicio}")
        self.stdout.write(f"url_categoria: {extractor.url_categoria}")
        self.stdout.write(f"pagina_prueba_url: {extractor.pagina_prueba_url}")
        self.stdout.write(f"dominio_permitido: {extractor.dominio_permitido}")
        self.stdout.write("No se procesaron productos.")
