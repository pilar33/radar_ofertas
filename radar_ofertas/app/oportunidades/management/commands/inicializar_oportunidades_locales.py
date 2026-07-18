from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from oportunidades.models import ComercioLocal, FuenteWeb, UmbralPrecioLocal
from oportunidades.services.categorias_service import asegurar_categorias_mercaderia_local


class Command(BaseCommand):
    help = "Inicializa categorias, comercios y umbrales base para oportunidades locales de Salta."

    def handle(self, *args, **options):
        resumen = asegurar_categorias_mercaderia_local()
        comercios = [
            ("Vea fisico", FuenteWeb.TIPO_SUPERMERCADO_FISICO, "Salta Capital"),
            ("Mayorista calle Oran", FuenteWeb.TIPO_MAYORISTA, "calle Oran, Salta Capital"),
            ("Mayorista local", FuenteWeb.TIPO_MAYORISTA, "Salta Capital"),
            ("Supermercado o mayorista", FuenteWeb.TIPO_SUPERMERCADO_FISICO, "Salta Capital"),
        ]
        creados = 0
        for nombre, tipo, zona in comercios:
            _, creado = ComercioLocal.objects.get_or_create(
                nombre=nombre,
                zona=zona,
                defaults={"tipo_fuente": tipo, "ciudad": "Salta Capital", "requiere_visita": True},
            )
            creados += int(creado)
        hoy = timezone.localdate()
        hasta = hoy + timedelta(days=90)
        umbrales = [
            ("Menudo de pollo economico", "menudos-carcasas-recortes", UmbralPrecioLocal.UNIDAD_KG, Decimal("500.00"), Decimal("300.00")),
            ("Fideos economicos segunda marca", "segundas-marcas", UmbralPrecioLocal.UNIDAD_KG, Decimal("1200.00"), Decimal("1000.00")),
            ("Aceite conveniente", "bebidas-distribuidoras", UmbralPrecioLocal.UNIDAD_LITRO, Decimal("3000.00"), Decimal("2500.00")),
            ("Papel higienico por metro", "papel-higienico-papel-cocina", UmbralPrecioLocal.UNIDAD_METRO, Decimal("40.00"), Decimal("30.00")),
        ]
        umbrales_creados = 0
        from oportunidades.models import CategoriaInteres

        for nombre, slug, unidad, bueno, fuerte in umbrales:
            categoria = CategoriaInteres.objects.filter(slug=slug).first()
            _, creado = UmbralPrecioLocal.objects.update_or_create(
                nombre=nombre,
                defaults={
                    "categoria": categoria,
                    "unidad_normalizada": unidad,
                    "precio_maximo_bueno": bueno,
                    "precio_maximo_fuerte": fuerte,
                    "fecha_desde": hoy,
                    "fecha_hasta": hasta,
                    "activo": True,
                    "origen_justificacion": "Umbral inicial editable para piloto local Salta.",
                },
            )
            umbrales_creados += int(creado)
        self.stdout.write(self.style.SUCCESS(f"Categorias creadas/actualizadas: {resumen}. Comercios nuevos: {creados}. Umbrales nuevos: {umbrales_creados}."))
