from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from oportunidades.models import CategoriaInteres, FuenteWeb, PrecioFuente, Producto, ProductoCanonico, ProductoFuente
from oportunidades.services.categorias_service import asegurar_categorias_base, clasificar_categoria_producto
from oportunidades.services.importacion_service import crear_o_actualizar_producto_fuente, obtener_o_crear_producto_canonico


class CategoriasProductosTests(TestCase):
    def setUp(self):
        asegurar_categorias_base()
        self.fuente = FuenteWeb.objects.create(
            nombre="Tienda prueba",
            url_base="https://tienda.example/",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            rubro_principal="herramientas",
        )

    def test_clasifica_herramientas_por_titulo(self):
        categoria = clasificar_categoria_producto(titulo="Taladro percutor inalambrico")

        self.assertEqual(categoria.slug, "herramientas")

    def test_clasifica_calzado_antes_que_marca_de_trabajo(self):
        categoria = clasificar_categoria_producto(
            titulo="Botin Pampero Seguridad Cuero",
            categoria_original="Indumentaria / Calzado de seguridad",
        )

        self.assertEqual(categoria.slug, "calzado")

    def test_producto_fuente_guarda_categoria_original_y_normalizada(self):
        categoria = clasificar_categoria_producto(titulo="Heladera No Frost Samsung", categoria_original="Electrodomesticos / Heladeras")
        row = {
            "titulo": "Heladera No Frost Samsung",
            "precio": Decimal("1000.00"),
            "url_producto": "https://tienda.example/heladera",
            "categoria": "Electrodomesticos / Heladeras",
            "subcategoria_original": "Heladeras",
            "etiquetas": "Samsung, no frost",
        }
        canonico, _ = obtener_o_crear_producto_canonico(row, categoria)
        producto_fuente, creado, _ = crear_o_actualizar_producto_fuente(row, self.fuente, categoria, canonico)

        self.assertTrue(creado)
        self.assertEqual(producto_fuente.categoria_original, "Electrodomesticos / Heladeras")
        self.assertEqual(producto_fuente.subcategoria_original, "Heladeras")
        self.assertEqual(producto_fuente.producto_canonico.categoria.slug, "electrodomesticos")

    def test_api_filtra_productos_fuente_por_categoria_normalizada(self):
        categoria = CategoriaInteres.objects.get(slug="herramientas")
        canonico = ProductoCanonico.objects.create(nombre_normalizado="taladro demo", categoria=categoria)
        producto = ProductoFuente.objects.create(
            producto_canonico=canonico,
            fuente_web=self.fuente,
            categoria_original="Herramientas electricas",
            titulo_original="Taladro demo",
            url_producto="https://tienda.example/taladro",
            condicion=Producto.CONDICION_NUEVO,
        )
        PrecioFuente.objects.create(producto_fuente=producto, precio=Decimal("1000.00"), precio_oportunidad=Decimal("1000.00"))

        response = self.client.get(reverse("oportunidades:api_productos"), {"categoria": "herramientas"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], producto.id)

    def test_api_lista_categorias_base(self):
        response = self.client.get(reverse("oportunidades:api_categorias"))

        self.assertEqual(response.status_code, 200)
        slugs = {item["slug"] for item in response.json()}
        self.assertIn("herramientas", slugs)
        self.assertIn("otros", slugs)
