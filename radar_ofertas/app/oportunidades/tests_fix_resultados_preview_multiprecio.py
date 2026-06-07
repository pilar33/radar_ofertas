from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase

from oportunidades.models import ConfiguracionExtractorWeb, ConectorFuente, FuenteWeb, PoliticaExtraccionFuente, PrecioFuente, ProductoFuente
from oportunidades.services.extractor_web_service import extraer_productos_preview
from oportunidades.services.procesamiento_preview_service import procesar_resultado_preview, validar_resultado_procesable


HTML_TIENDANUBE = """
<html><body>
  <div class="js-item-product item-product">
    <a class="js-product-item-image-link-private" href="/productos/set-salero-bambu/">
      <img class="js-product-item-image-private" data-src="https://dcdn.mitiendanube.com/stores/001/products/salero.webp">
    </a>
    <a class="js-item-name item-name" href="/productos/set-salero-bambu/">Set Salero y Pimentero Bambu</a>
    <div class="js-item-price-container">
      <span class="js-price-display">$ 35.700,00</span>
    </div>
    <div class="ts-custom-discount payment-discount-price-product-container">
      <span class="payment-discount-price-product">$ 20.990,20</span>
      <span>con</span>
      <span>Transferencia</span>
    </div>
    <div class="js-max-installments-container">6 cuotas sin interes de $ 4.997,67</div>
  </div>
</body></html>
"""


class FixResultadosPreviewMultiprecioTests(TestCase):
    def setUp(self):
        self.fuente = FuenteWeb.objects.create(
            nombre="Ganga Home",
            url_base="https://www.gangahome.com.ar/",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            rubro_principal="hogar/deco",
            activa=True,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            permite_scraping=True,
            robots_txt_revisado=True,
            terminos_revisados=True,
            requiere_login=False,
            tiene_captcha=False,
        )
        self.conector = ConectorFuente.objects.create(
            fuente_web=self.fuente,
            nombre="Ganga Home - Extractor",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_revision_manual=False,
            respeta_politica_fuente=True,
        )
        self.extractor = ConfiguracionExtractorWeb.objects.create(
            conector=self.conector,
            url_inicio="https://www.gangahome.com.ar/",
            url_categoria="https://www.gangahome.com.ar/cocina/",
            pagina_prueba_url="https://www.gangahome.com.ar/cocina/",
            dominio_permitido="gangahome.com.ar",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_MIXTO,
            max_paginas=1,
            max_productos=10,
            delay_segundos=Decimal("2.00"),
            habilitado=True,
            solo_preview=True,
        )

    def ejecutar_preview_mock(self, html=HTML_TIENDANUBE):
        with patch(
            "oportunidades.services.extractor_web_service.hacer_request_extractor",
            return_value={"ok": True, "status_code": 200, "content_type": "text/html", "text": html, "error": ""},
        ):
            ejecucion = extraer_productos_preview(self.conector)
        return ejecucion.resultados_web.first()

    def test_preview_extractor_tiendanube_guarda_url_real(self):
        resultado = self.ejecutar_preview_mock()

        self.assertEqual(resultado.url_producto, "https://www.gangahome.com.ar/productos/set-salero-bambu/")

    def test_preview_extractor_tiendanube_guarda_imagen(self):
        resultado = self.ejecutar_preview_mock()

        self.assertIn("mitiendanube", resultado.imagen_url)

    def test_preview_extractor_tiendanube_guarda_precio_lista(self):
        resultado = self.ejecutar_preview_mock()

        self.assertEqual(resultado.precio_lista_decimal, Decimal("35700.00"))

    def test_preview_extractor_tiendanube_guarda_precio_transferencia(self):
        resultado = self.ejecutar_preview_mock()

        self.assertEqual(resultado.precio_transferencia_decimal, Decimal("20990.20"))

    def test_preview_extractor_tiendanube_guarda_precio_oportunidad(self):
        resultado = self.ejecutar_preview_mock()

        self.assertEqual(resultado.precio_oportunidad_decimal, Decimal("20990.20"))
        self.assertEqual(resultado.precio_decimal, Decimal("20990.20"))
        self.assertEqual(resultado.tipo_precio_oportunidad, PrecioFuente.TIPO_PRECIO_TRANSFERENCIA)

    def test_resultados_preview_muestra_multiprecio(self):
        self.ejecutar_preview_mock()

        response = Client(HTTP_HOST="localhost").get(f"/extractores/{self.extractor.pk}/resultados/")

        self.assertContains(response, "Transferencia")
        self.assertContains(response, "Oportunidad")
        self.assertContains(response, "Abrir")
        self.assertContains(response, "img")

    def test_procesar_preview_usa_precio_oportunidad(self):
        resultado = self.ejecutar_preview_mock()

        procesar_resultado_preview(resultado)
        precio = PrecioFuente.objects.get()

        self.assertEqual(precio.precio, Decimal("20990.20"))
        self.assertEqual(precio.precio_oportunidad, Decimal("20990.20"))

    def test_procesar_preview_guarda_precio_transferencia(self):
        resultado = self.ejecutar_preview_mock()

        procesar_resultado_preview(resultado)
        precio = PrecioFuente.objects.get()

        self.assertEqual(precio.precio_transferencia, Decimal("20990.20"))
        self.assertEqual(precio.tipo_precio_oportunidad, PrecioFuente.TIPO_PRECIO_TRANSFERENCIA)

    def test_procesar_preview_guarda_imagen_y_url(self):
        resultado = self.ejecutar_preview_mock()

        procesar_resultado_preview(resultado)
        producto = ProductoFuente.objects.get()

        self.assertEqual(producto.url_producto, "https://www.gangahome.com.ar/productos/set-salero-bambu/")
        self.assertIn("mitiendanube", producto.imagen_url)

    def test_resultado_preview_sin_url_marca_revision(self):
        html = HTML_TIENDANUBE.replace('href="/productos/set-salero-bambu/"', 'href="/cuenta/"')
        resultado = self.ejecutar_preview_mock(html)

        validacion = validar_resultado_procesable(resultado)

        self.assertEqual(validacion["nivel"], "advertencia")
        self.assertIn("sin URL real", validacion["mensaje"])
