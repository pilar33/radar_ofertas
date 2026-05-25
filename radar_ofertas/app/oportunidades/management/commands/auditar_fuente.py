from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import FuenteWeb
from oportunidades.services.auditoria_fuentes_service import auditar_fuente_basica, interpretar_auditoria


class Command(BaseCommand):
    help = "Audita home, robots.txt y sitemap de una fuente sin extraer productos."

    def add_arguments(self, parser):
        parser.add_argument("--fuente-id", type=int, required=True)

    def handle(self, *args, **options):
        try:
            fuente = FuenteWeb.objects.get(pk=options["fuente_id"])
        except FuenteWeb.DoesNotExist as exc:
            raise CommandError("Fuente no encontrada.") from exc
        auditoria = auditar_fuente_basica(fuente)
        self.stdout.write(self.style.SUCCESS("Auditoria finalizada."))
        self.stdout.write(interpretar_auditoria(auditoria))
        self.stdout.write(f"Semaforo sugerido: {auditoria.semaforo_sugerido}")
        self.stdout.write(f"Metodo recomendado: {auditoria.metodo_recomendado}")
        self.stdout.write("Requiere revision manual antes de automatizar.")
