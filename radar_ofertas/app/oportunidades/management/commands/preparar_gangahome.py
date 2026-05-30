import os

from django.core.management.base import BaseCommand, CommandError

from oportunidades.services.wizard_fuentes_service import preparar_fuente_generica


class Command(BaseCommand):
    help = "Prepara GangaHome como segunda fuente real candidata sin activar scraping."

    def add_arguments(self, parser):
        parser.add_argument("--url-base", default=os.getenv("GANGAHOME_URL_BASE", ""))
        parser.add_argument("--rubro", default="hogar/deco")

    def handle(self, *args, **options):
        if not options["url_base"]:
            raise CommandError("Indicar --url-base o configurar GANGAHOME_URL_BASE.")
        fuente, conector, creada, conector_creado = preparar_fuente_generica(
            "GangaHome",
            options["url_base"],
            options["rubro"],
        )
        self.stdout.write(self.style.SUCCESS("GangaHome preparada como fuente candidata."))
        self.stdout.write(f"Fuente ID: {fuente.pk} ({'creada' if creada else 'existente'})")
        self.stdout.write(f"Conector ID: {conector.pk} ({'creado' if conector_creado else 'existente'})")
        self.stdout.write("Estado: pendiente de auditoria, revision manual y selectores.")
