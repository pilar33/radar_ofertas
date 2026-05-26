from django.core.management.base import BaseCommand, CommandError

from oportunidades.management.commands.preparar_decohome import preparar_decohome
from oportunidades.models import RevisionManualFuente
from oportunidades.services.revision_fuentes_service import crear_revision_manual


class Command(BaseCommand):
    help = "Registra una revision manual de Deco Home sin inventar resultados."

    def add_arguments(self, parser):
        parser.add_argument("--tipo", required=True, choices=[c[0] for c in RevisionManualFuente.TIPO_CHOICES])
        parser.add_argument("--resultado", required=True, choices=[c[0] for c in RevisionManualFuente.RESULTADO_CHOICES])
        parser.add_argument("--url", default="")
        parser.add_argument("--resumen", required=True)
        parser.add_argument("--decision", default="")
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **options):
        if options["resultado"] == RevisionManualFuente.RESULTADO_PERMITE and options["aplicar"] and not options["decision"]:
            raise CommandError("Para aplicar resultado=permite se requiere --decision explicita.")
        fuente, _ = preparar_decohome()
        revision, politica = crear_revision_manual(
            {
                "fuente_web": fuente,
                "tipo_revision": options["tipo"],
                "resultado": options["resultado"],
                "url_revisada": options["url"] or None,
                "resumen": options["resumen"],
                "decision": options["decision"] or None,
            },
            aplicar=options["aplicar"],
        )
        self.stdout.write(self.style.SUCCESS("Revision Deco Home registrada."))
        self.stdout.write(f"Revision ID: {revision.pk}")
        if politica:
            self.stdout.write(f"Politica actualizada: semaforo={politica.semaforo}, scraping={politica.permite_scraping}")
