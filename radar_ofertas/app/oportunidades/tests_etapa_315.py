from decimal import Decimal
from pathlib import Path

from django.test import Client, TestCase

from oportunidades.models import CategoriaInteres, FuenteWeb, PrecioFuente, ProductoCanonico, ProductoFuente
from oportunidades.services.validacion_dataset_service import validar_dataset_piloto


class Etapa315ValidacionPilotoTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(nombre="Hogar", palabra_clave="hogar")
        self.fuente = FuenteWeb.objects.create(
            nombre="Ganga Home",
            url_base="https://www.gangahome.com.ar/",
            tipo_fuente="tienda_online",
            rubro_principal="hogar/deco",
        )
        self.canonico = ProductoCanonico.objects.create(
            nombre_normalizado="set salero bambu",
            categoria=self.categoria,
        )

    def crear_producto(self, titulo="Set Salero Bambu", url="https://www.gangahome.com.ar/productos/set-salero/"):
        return ProductoFuente.objects.create(
            producto_canonico=self.canonico,
            fuente_web=self.fuente,
            titulo_original=titulo,
            url_producto=url,
            imagen_url="https://www.gangahome.com.ar/img/set.jpg",
            condicion="nuevo",
            disponible=True,
        )

    def crear_precio(self, producto, oportunidad=Decimal("12000.00"), transferencia=Decimal("12000.00")):
        return PrecioFuente.objects.create(
            producto_fuente=producto,
            precio=oportunidad,
            precio_lista=Decimal("15000.00"),
            precio_transferencia=transferencia,
            precio_oportunidad=oportunidad,
            tipo_precio_oportunidad=PrecioFuente.TIPO_PRECIO_TRANSFERENCIA,
            moneda="ARS",
            origen_dato=PrecioFuente.ORIGEN_SCRAPING,
        )

    def test_validar_dataset_piloto_carga(self):
        resumen = validar_dataset_piloto()

        self.assertIn("total_productos", resumen)
        self.assertIn("dataset_apto", resumen)

    def test_validacion_detecta_productos_sin_imagen(self):
        producto = self.crear_producto()
        producto.imagen_url = ""
        producto.save(update_fields=["imagen_url"])
        self.crear_precio(producto)

        resumen = validar_dataset_piloto()

        self.assertEqual(resumen["sin_imagen"], 1)

    def test_validacion_detecta_productos_sin_precio_oportunidad(self):
        producto = self.crear_producto()
        PrecioFuente.objects.create(
            producto_fuente=producto,
            precio=Decimal("15000.00"),
            precio_lista=Decimal("15000.00"),
            precio_oportunidad=Decimal("0.00"),
            tipo_precio_oportunidad=PrecioFuente.TIPO_PRECIO_DESCONOCIDO,
            moneda="ARS",
            origen_dato=PrecioFuente.ORIGEN_SCRAPING,
        )

        resumen = validar_dataset_piloto()

        self.assertEqual(resumen["sin_precio_oportunidad"], 1)

    def test_validacion_detecta_url_tecnica(self):
        producto = self.crear_producto(url="https://radar.local/producto-tecnico/1")
        producto.url_tecnica_generada = True
        producto.save(update_fields=["url_tecnica_generada"])
        self.crear_precio(producto)

        resumen = validar_dataset_piloto()

        self.assertEqual(resumen["url_tecnica"], 1)
        self.assertEqual(resumen["sin_url"], 1)

    def test_validacion_dataset_apto_si_datos_minimos_ok(self):
        producto = self.crear_producto()
        self.crear_precio(producto)

        resumen = validar_dataset_piloto()

        self.assertTrue(resumen["dataset_apto"])
        self.assertEqual(resumen["con_transferencia"], 1)
        self.assertEqual(resumen["lista_mayor_transferencia"], 1)

    def test_vista_validacion_piloto_carga(self):
        response = Client(HTTP_HOST="localhost").get("/dataset/validacion-piloto/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Validacion dataset piloto")

    def test_manual_operativo_contiene_carga_piloto(self):
        manual = Path(__file__).resolve().parents[1] / "docs" / "manual_operativo_radar.md"

        self.assertIn("Carga piloto real en SQL Server", manual.read_text(encoding="utf-8"))

    def test_no_usa_render_sqlite_como_dataset_real_en_documentacion(self):
        doc = Path(__file__).resolve().parents[1] / "docs" / "flujo_piloto_datos_reales.md"
        contenido = doc.read_text(encoding="utf-8")

        self.assertIn("Render con SQLite queda solo como demo/staging", contenido)
        self.assertIn("Si el diagnostico indica SQLite, no cargar dataset real", contenido)
