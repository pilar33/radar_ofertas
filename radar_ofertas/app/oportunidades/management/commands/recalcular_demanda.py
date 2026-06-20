from django.core.management.base import BaseCommand

from oportunidades.models import ProductoFuente
from oportunidades.services.demanda_service import actualizar_demanda_por_fuentes, recalcular_demanda_producto
from oportunidades.services.ranking_comercial_service import calcular_score_comercial_producto_fuente


class Command(BaseCommand):
    help = "Recalcula demanda estimada y resumen comercial sin inventar ventas."

    def add_arguments(self, parser):
        parser.add_argument("--producto-fuente-id", type=int)
        parser.add_argument("--producto-canonico-id", type=int)
        parser.add_argument("--fuente-id", type=int)
        parser.add_argument("--limite", type=int)

    def handle(self, *args, **options):
        productos = ProductoFuente.objects.select_related("fuente_web", "producto_canonico").prefetch_related("senales_demanda")
        if options.get("producto_fuente_id"):
            productos = productos.filter(pk=options["producto_fuente_id"])
        if options.get("producto_canonico_id"):
            productos = productos.filter(producto_canonico_id=options["producto_canonico_id"])
        if options.get("fuente_id"):
            productos = productos.filter(fuente_web_id=options["fuente_id"])
        if options.get("limite"):
            productos = productos[: options["limite"]]
        productos = list(productos)
        canonicos = {producto.producto_canonico for producto in productos if producto.producto_canonico_id}
        for canonico in canonicos:
            actualizar_demanda_por_fuentes(canonico)
        procesados = 0
        for producto in productos:
            if not producto.producto_canonico_id:
                recalcular_demanda_producto(producto)
            calcular_score_comercial_producto_fuente(producto)
            procesados += 1
        self.stdout.write(self.style.SUCCESS(f"Demanda recalculada. Productos: {procesados}. Canonicos: {len(canonicos)}."))
