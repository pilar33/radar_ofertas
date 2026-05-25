from django.core.management.base import BaseCommand

from oportunidades.management.commands.preparar_decohome import preparar_decohome
from oportunidades.services.auditoria_fuentes_service import auditar_fuente_basica, interpretar_auditoria


class Command(BaseCommand):
    help = "Prepara y audita Deco Home sin scraping de productos."

    def handle(self, *args, **options):
        fuente, _ = preparar_decohome()
        auditoria = auditar_fuente_basica(fuente)
        self.stdout.write(self.style.SUCCESS("Auditoria Deco Home finalizada."))
        self.stdout.write(interpretar_auditoria(auditoria))
        self.stdout.write(f"Semaforo sugerido: {auditoria.semaforo_sugerido}")
        self.stdout.write(f"Metodo recomendado: {auditoria.metodo_recomendado}")
