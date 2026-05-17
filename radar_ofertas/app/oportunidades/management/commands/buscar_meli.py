from django.core.management.base import BaseCommand, CommandError

from oportunidades.models import CategoriaInteres
from oportunidades.services.mercado_libre_service import sincronizar_busqueda_meli


class Command(BaseCommand):
    help = "Busca productos en la API publica de Mercado Libre y genera oportunidades."

    def add_arguments(self, parser):
        parser.add_argument("--query", type=str, help="Texto de busqueda.")
        parser.add_argument("--categoria-id", type=int, help="ID de CategoriaInteres.")
        parser.add_argument("--limit", type=int, default=20, help="Cantidad maxima de resultados.")
        parser.add_argument("--offset", type=int, default=0, help="Offset de resultados.")

    def handle(self, *args, **options):
        categoria = None
        query = options.get("query")

        categoria_id = options.get("categoria_id")
        if categoria_id:
            try:
                categoria = CategoriaInteres.objects.get(pk=categoria_id)
            except CategoriaInteres.DoesNotExist as exc:
                raise CommandError(f"No existe CategoriaInteres con id {categoria_id}.") from exc

        if not query and categoria:
            query = categoria.palabra_clave

        if not query:
            raise CommandError("Debe indicar --query o --categoria-id con una categoria valida.")

        resumen = sincronizar_busqueda_meli(
            query,
            categoria=categoria,
            limit=options["limit"],
            offset=options["offset"],
        )

        self.stdout.write(self.style.SUCCESS("Busqueda Mercado Libre finalizada."))
        self.stdout.write(f"Query: {resumen['query']}")
        self.stdout.write(f"Procesados: {resumen['procesados']}")
        self.stdout.write(f"Creados: {resumen['creados']}")
        self.stdout.write(f"Actualizados: {resumen['actualizados']}")
        self.stdout.write(f"Errores: {resumen['errores']}")
