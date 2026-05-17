import time

from django.core.management.base import BaseCommand

from oportunidades.models import CategoriaInteres
from oportunidades.services.mercado_libre_service import sincronizar_busqueda_meli


class Command(BaseCommand):
    help = "Busca productos en Mercado Libre para todas las categorias activas."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Cantidad maxima de resultados por categoria.")
        parser.add_argument("--delay", type=float, default=2, help="Demora en segundos entre consultas.")

    def handle(self, *args, **options):
        categorias = CategoriaInteres.objects.filter(activa=True).order_by("prioridad", "nombre")
        total_procesados = 0
        total_creados = 0
        total_actualizados = 0
        total_errores = 0

        for index, categoria in enumerate(categorias):
            resumen = sincronizar_busqueda_meli(
                categoria.palabra_clave,
                categoria=categoria,
                limit=options["limit"],
            )
            total_procesados += resumen["procesados"]
            total_creados += resumen["creados"]
            total_actualizados += resumen["actualizados"]
            total_errores += resumen["errores"]

            self.stdout.write(
                f"{categoria.nombre}: {resumen['procesados']} procesados, "
                f"{resumen['creados']} creados, {resumen['actualizados']} actualizados, "
                f"{resumen['errores']} errores."
            )

            if index < categorias.count() - 1:
                time.sleep(options["delay"])

        self.stdout.write(self.style.SUCCESS("Busqueda por categorias finalizada."))
        self.stdout.write(f"Procesados: {total_procesados}")
        self.stdout.write(f"Creados: {total_creados}")
        self.stdout.write(f"Actualizados: {total_actualizados}")
        self.stdout.write(f"Errores: {total_errores}")
