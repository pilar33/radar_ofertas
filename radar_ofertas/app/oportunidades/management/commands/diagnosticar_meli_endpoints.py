from django.core.management.base import BaseCommand

from oportunidades.services.mercado_libre_service import diagnosticar_endpoints_meli


class Command(BaseCommand):
    help = "Diagnostica endpoints oficiales de Mercado Libre con y sin token."

    def add_arguments(self, parser):
        parser.add_argument("--query", type=str, default="calza mujer", help="Query para probar /sites/MLA/search.")
        parser.add_argument("--item-id", type=str, default="MLA3092462776", help="Item ID para probar /items/{item_id}.")
        parser.add_argument("--limit", type=int, default=1, help="Limite para la busqueda.")

    def handle(self, *args, **options):
        diagnostico = diagnosticar_endpoints_meli(
            query=options["query"],
            item_id=options["item_id"],
            limit=options["limit"],
        )

        self.stdout.write(f"Query: {diagnostico['query']}")
        self.stdout.write(f"Item ID: {diagnostico['item_id']}")
        self.stdout.write(f"Token disponible: {'si' if diagnostico['token_disponible'] else 'no'}")
        self.stdout.write("")

        for resultado in diagnostico["resultados"]:
            self.stdout.write(f"Endpoint: {resultado['nombre']}")
            self.stdout.write(f"  usa token: {'si' if resultado['usa_token'] else 'no'}")
            self.stdout.write(f"  status_code: {resultado['status_code']}")
            self.stdout.write(f"  ok: {'si' if resultado['ok'] else 'no'}")
            if resultado.get("error"):
                self.stdout.write(f"  error: {resultado['error']}")
            if resultado.get("response_text"):
                self.stdout.write(f"  respuesta: {resultado['response_text'][:500]}")
            self.stdout.write("")

        self.stdout.write("Interpretacion:")
        self.stdout.write(diagnostico["interpretacion"])
