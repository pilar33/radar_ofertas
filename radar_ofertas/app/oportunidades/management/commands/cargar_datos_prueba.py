from decimal import Decimal

from django.core.management.base import BaseCommand

from oportunidades.models import (
    CategoriaInteres,
    ContenidoSugerido,
    FuenteProducto,
    Oportunidad,
    PrecioProducto,
    Producto,
)
from oportunidades.services.clasificacion_service import clasificar_oportunidad
from oportunidades.services.contenido_service import generar_contenido_basico


class Command(BaseCommand):
    help = "Carga datos simulados para probar radar_ofertas."

    def handle(self, *args, **options):
        fuentes = self._crear_fuentes()
        categorias = self._crear_categorias()
        productos = self._crear_productos(fuentes, categorias)
        oportunidades = self._crear_oportunidades(productos)

        self.stdout.write(self.style.SUCCESS(f"Datos de prueba listos: {len(oportunidades)} oportunidades."))

    def _crear_fuentes(self):
        mercado_libre, _ = FuenteProducto.objects.get_or_create(
            nombre="Mercado Libre",
            defaults={
                "tipo": FuenteProducto.TIPO_MARKETPLACE,
                "url_base": "https://www.mercadolibre.com.ar",
                "activa": True,
            },
        )
        manual, _ = FuenteProducto.objects.get_or_create(
            nombre="Manual",
            defaults={
                "tipo": FuenteProducto.TIPO_MANUAL,
                "activa": True,
            },
        )
        return {"mercado_libre": mercado_libre, "manual": manual}

    def _crear_categorias(self):
        datos = [
            ("Cocina/Emprendimiento", "cocina emprendimiento", 1),
            ("Organizacion", "organizador", 2),
            ("Tecnologia economica", "gadget economico", 3),
            ("Seguridad", "seguridad hogar", 4),
            ("Hogar", "hogar practico", 5),
        ]
        categorias = {}

        for nombre, palabra_clave, prioridad in datos:
            categoria, _ = CategoriaInteres.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "palabra_clave": palabra_clave,
                    "prioridad": prioridad,
                    "activa": True,
                },
            )
            categorias[nombre] = categoria

        return categorias

    def _crear_productos(self, fuentes, categorias):
        datos = [
            {
                "codigo_externo": "MLA-1001",
                "titulo": "Selladora de bolsas compacta",
                "url": "https://example.com/productos/selladora-bolsas",
                "marca": "KitchenPro",
                "categoria": categorias["Cocina/Emprendimiento"],
                "fuente": fuentes["mercado_libre"],
                "vendedor": "Todo Cocina",
                "reputacion_vendedor": "verde",
                "condicion": Producto.CONDICION_NUEVO,
                "es_chico_liviano": True,
                "es_fragil": False,
                "precios": [Decimal("8500"), Decimal("7900")],
                "reventa": Decimal("12000"),
            },
            {
                "codigo_externo": "MLA-1002",
                "titulo": "Organizador plegable para placard",
                "url": "https://example.com/productos/organizador-placard",
                "marca": "OrdenYa",
                "categoria": categorias["Organizacion"],
                "fuente": fuentes["mercado_libre"],
                "vendedor": "Casa Ordenada",
                "reputacion_vendedor": "verde",
                "condicion": Producto.CONDICION_NUEVO,
                "es_chico_liviano": True,
                "es_fragil": False,
                "precios": [Decimal("4300"), Decimal("3900")],
                "reventa": Decimal("6200"),
            },
            {
                "codigo_externo": "MLA-1003",
                "titulo": "Mini aro de luz USB para celular",
                "url": "https://example.com/productos/aro-luz-usb",
                "marca": "Glow",
                "categoria": categorias["Tecnologia economica"],
                "fuente": fuentes["mercado_libre"],
                "vendedor": "Tecno Express",
                "reputacion_vendedor": "amarilla",
                "condicion": Producto.CONDICION_NUEVO,
                "es_chico_liviano": True,
                "es_fragil": False,
                "precios": [Decimal("6100"), Decimal("5900")],
                "reventa": Decimal("7600"),
            },
            {
                "codigo_externo": "MAN-1004",
                "titulo": "Traba magnetica para cajones",
                "url": "https://example.com/productos/traba-magnetica",
                "marca": "SafeHome",
                "categoria": categorias["Seguridad"],
                "fuente": fuentes["manual"],
                "vendedor": "Proveedor local",
                "reputacion_vendedor": "sin datos",
                "condicion": Producto.CONDICION_NUEVO,
                "es_chico_liviano": True,
                "es_fragil": False,
                "precios": [Decimal("2200"), Decimal("2100")],
                "reventa": Decimal("3500"),
            },
            {
                "codigo_externo": "MLA-1005",
                "titulo": "Dispenser automatico de jabon",
                "url": "https://example.com/productos/dispenser-jabon",
                "marca": "CleanBox",
                "categoria": categorias["Hogar"],
                "fuente": fuentes["mercado_libre"],
                "vendedor": "Hogar Total",
                "reputacion_vendedor": "verde",
                "condicion": Producto.CONDICION_NUEVO,
                "es_chico_liviano": True,
                "es_fragil": True,
                "precios": [Decimal("9800"), Decimal("9400")],
                "reventa": Decimal("11800"),
            },
            {
                "codigo_externo": "MLA-1006",
                "titulo": "Set de moldes de silicona para snacks",
                "url": "https://example.com/productos/moldes-silicona",
                "marca": "BakeMini",
                "categoria": categorias["Cocina/Emprendimiento"],
                "fuente": fuentes["mercado_libre"],
                "vendedor": "Mundo Reposteria",
                "reputacion_vendedor": "verde",
                "condicion": Producto.CONDICION_NUEVO,
                "es_chico_liviano": True,
                "es_fragil": False,
                "precios": [Decimal("5100"), Decimal("4700")],
                "reventa": Decimal("7200"),
            },
            {
                "codigo_externo": "MAN-1007",
                "titulo": "Soporte adhesivo multiuso para pared",
                "url": "https://example.com/productos/soporte-adhesivo",
                "marca": "FixUp",
                "categoria": categorias["Hogar"],
                "fuente": fuentes["manual"],
                "vendedor": "Distribuidora Oeste",
                "reputacion_vendedor": "sin datos",
                "condicion": Producto.CONDICION_NUEVO,
                "es_chico_liviano": True,
                "es_fragil": False,
                "precios": [Decimal("1800"), Decimal("1750")],
                "reventa": Decimal("2600"),
            },
            {
                "codigo_externo": "MLA-1008",
                "titulo": "Camara falsa de seguridad con LED",
                "url": "https://example.com/productos/camara-falsa-led",
                "marca": "SecuLook",
                "categoria": categorias["Seguridad"],
                "fuente": fuentes["mercado_libre"],
                "vendedor": "Seguridad Express",
                "reputacion_vendedor": "amarilla",
                "condicion": Producto.CONDICION_NUEVO,
                "es_chico_liviano": True,
                "es_fragil": False,
                "precios": [Decimal("7200"), Decimal("6900")],
                "reventa": Decimal("8900"),
            },
        ]

        productos = []
        for item in datos:
            precios = item.pop("precios")
            reventa = item.pop("reventa")
            producto, _ = Producto.objects.update_or_create(
                codigo_externo=item["codigo_externo"],
                defaults=item,
            )
            producto.precio_reventa_prueba = reventa

            for precio in precios:
                PrecioProducto.objects.get_or_create(
                    producto=producto,
                    precio=precio,
                    defaults={"costo_envio": Decimal("0"), "moneda": "ARS"},
                )

            productos.append(producto)

        return productos

    def _crear_oportunidades(self, productos):
        oportunidades = []

        for producto in productos:
            ultimo_precio = producto.precios.order_by("-fecha_relevamiento", "-id").first()
            precio_actual = ultimo_precio.precio if ultimo_precio else Decimal("0")
            precio_reventa = producto.precio_reventa_prueba
            evaluacion = clasificar_oportunidad(producto, precio_actual, precio_reventa)

            oportunidad, _ = Oportunidad.objects.update_or_create(
                producto=producto,
                defaults={
                    "precio_referencia": precio_actual,
                    "precio_actual": precio_actual,
                    "precio_reventa_estimado": precio_reventa,
                    "margen_estimado": evaluacion["margen_estimado"],
                    "porcentaje_margen": evaluacion["porcentaje_margen"],
                    "tipo": evaluacion["tipo"],
                    "puntaje": evaluacion["puntaje"],
                    "riesgo": evaluacion["riesgo"],
                    "motivo": evaluacion["motivo"],
                    "estado": Oportunidad.ESTADO_PENDIENTE,
                },
            )

            if not oportunidad.contenidos.exists():
                ContenidoSugerido.objects.create(
                    oportunidad=oportunidad,
                    **generar_contenido_basico(oportunidad),
                )

            oportunidades.append(oportunidad)

        return oportunidades
