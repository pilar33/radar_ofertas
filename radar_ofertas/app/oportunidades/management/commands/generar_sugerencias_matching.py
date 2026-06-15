from django.core.management.base import BaseCommand

from oportunidades.services.matching_productos_service import generar_sugerencias_matching


class Command(BaseCommand):
    help = "Genera sugerencias controladas de matching entre productos por fuente."

    def add_arguments(self, parser):
        parser.add_argument("--fuente-id", type=int)
        parser.add_argument("--limite", type=int, default=500)
        parser.add_argument("--min-score", type=int, default=60)
        parser.add_argument("--incluir-misma-fuente", action="store_true")

    def handle(self, *args, **options):
        resumen = generar_sugerencias_matching(
            fuente_id=options.get("fuente_id"),
            limite=options["limite"],
            min_score=options["min_score"],
            incluir_misma_fuente=options["incluir_misma_fuente"],
        )
        self.stdout.write(f"Productos evaluados: {resumen['productos_evaluados']}")
        self.stdout.write(f"Comparaciones: {resumen['comparaciones']}")
        self.stdout.write(self.style.SUCCESS(f"Sugerencias creadas: {resumen['creadas']}"))
        self.stdout.write(f"Omitidas: {resumen['omitidas']}")
        self.stdout.write(f"Duplicadas: {resumen['duplicadas']}")
        self.stdout.write(f"Errores: {resumen['errores']}")
