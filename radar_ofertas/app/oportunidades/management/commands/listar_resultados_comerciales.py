from django.core.management.base import BaseCommand

from oportunidades.models import ResultadoComercialProducto


class Command(BaseCommand):
    help = "Lista resultados comerciales reales."

    def add_arguments(self, parser):
        parser.add_argument("--estado")
        parser.add_argument("--limite", type=int, default=20)

    def handle(self, *args, **options):
        resultados = ResultadoComercialProducto.objects.select_related("candidato", "producto_fuente")
        if options["estado"]:
            resultados = resultados.filter(estado_resultado=options["estado"])
        total = 0
        for resultado in resultados.order_by("-fecha_actualizacion")[: options["limite"]]:
            self.stdout.write(
                f"#{resultado.candidato_id} | {resultado.producto_fuente or '-'} | "
                f"compradas={resultado.cantidad_comprada_total} vendidas={resultado.cantidad_vendida_total} | "
                f"ganancia={resultado.ganancia_neta_total} margen={resultado.margen_real_pct:.2f}% | {resultado.estado_resultado}"
            )
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Resultados mostrados: {total}"))
