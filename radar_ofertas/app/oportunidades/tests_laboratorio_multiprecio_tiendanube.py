from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from oportunidades.models import PrecioFuente
from oportunidades.services.extractor_web_service import (
    detectar_bloqueos_html,
    detectar_plataforma_ecommerce,
    extraer_css_productos,
    extraer_imagen_producto,
    extraer_precios_multiples_desde_texto,
    extraer_titulo_producto,
    extraer_url_producto,
    obtener_preset_selectores_tiendanube,
)
from oportunidades.services.laboratorio_mapeo_service import analizar_url_laboratorio


class LaboratorioMultiprecioTiendaNubeTests(TestCase):
    def _response(self, html, status=200, content_type="text/html"):
        response = Mock()
        response.status_code = status
        response.headers = {"Content-Type": content_type}
        response.encoding = "utf-8"
        response.iter_content.return_value = [html.encode("utf-8")]
        return response

    def _tiendanube_html(self):
        return """
        <html>
          <body>
            <nav><a href="/account/login">Mi cuenta</a><a href="/cart">Carrito</a></nav>
            <div class="js-item-product item-product">
              <a class="js-product-item-image-link-private" href="/productos/alfombra-demo" title="Alfombra Nordica">
                <img class="js-product-item-image-private" data-src="//dcdn.mitiendanube.com/stores/1/products/alfombra.webp">
              </a>
              <div class="js-item-name">Alfombra Nordica</div>
              <div class="js-price-display">$ 25.000</div>
              <div class="js-payment-discount">Precio transferencia $ 21.500</div>
              <div>3 cuotas sin interes de $ 8.333</div>
            </div>
          </body>
        </html>
        """

    def test_detectar_plataforma_tiendanube(self):
        self.assertEqual(detectar_plataforma_ecommerce(self._tiendanube_html()), "tiendanube")

    def test_preset_tiendanube_no_usa_align_items_center(self):
        preset = obtener_preset_selectores_tiendanube()

        self.assertNotIn("align-items-center", preset["product_card_selector"])
        self.assertIn("js-item-product", preset["product_card_selector"])

    def test_extraer_url_producto_tiendanube(self):
        from bs4 import BeautifulSoup

        card = BeautifulSoup(self._tiendanube_html(), "lxml").select_one(".js-item-product")

        self.assertEqual(extraer_url_producto(card, "https://ganga.example/categoria"), "https://ganga.example/productos/alfombra-demo")

    def test_extraer_titulo_desde_title_link_tiendanube(self):
        from bs4 import BeautifulSoup

        html = '<div class="js-item-product"><a href="/productos/p" title="Producto desde title"><img src="/i.webp"></a><span>$ 1.200</span></div>'
        card = BeautifulSoup(html, "lxml").select_one(".js-item-product")

        self.assertEqual(extraer_titulo_producto(card), "Producto desde title")

    def test_extraer_imagen_desde_src(self):
        from bs4 import BeautifulSoup

        card = BeautifulSoup('<div><img src="/img.jpg"></div>', "lxml").div

        self.assertEqual(extraer_imagen_producto(card, "https://example.com/c"), "https://example.com/img.jpg")

    def test_extraer_imagen_desde_data_src(self):
        from bs4 import BeautifulSoup

        card = BeautifulSoup('<div><img data-src="//cdn.example.com/img.webp"></div>', "lxml").div

        self.assertEqual(extraer_imagen_producto(card, "https://example.com/c"), "https://cdn.example.com/img.webp")

    def test_extraer_imagen_desde_srcset(self):
        from bs4 import BeautifulSoup

        card = BeautifulSoup('<div><img srcset="/small.jpg 320w, /large.webp 800w"></div>', "lxml").div

        self.assertEqual(extraer_imagen_producto(card, "https://example.com/c"), "https://example.com/large.webp")

    def test_extraer_imagen_desde_data_append_images(self):
        from bs4 import BeautifulSoup

        card = BeautifulSoup('<div data-append-images="https://cdn.example.com/foto.png"></div>', "lxml").div

        self.assertEqual(extraer_imagen_producto(card, "https://example.com/c"), "https://cdn.example.com/foto.png")

    def test_extraer_precios_multiples_transferencia(self):
        datos = extraer_precios_multiples_desde_texto("$ 25.000 Precio transferencia $ 21.500")

        self.assertEqual(datos["precio_transferencia_decimal"], Decimal("21500.00"))
        self.assertEqual(datos["precio_oportunidad_decimal"], Decimal("21500.00"))
        self.assertEqual(datos["tipo_precio_oportunidad"], PrecioFuente.TIPO_PRECIO_TRANSFERENCIA)

    def test_extraer_precios_multiples_lista_y_transferencia(self):
        datos = extraer_precios_multiples_desde_texto("Lista $ 30.000 Transferencia $ 24.000")

        self.assertEqual(datos["precio_lista_decimal"], Decimal("30000.00"))
        self.assertEqual(datos["precio_transferencia_decimal"], Decimal("24000.00"))

    def test_extraer_cuotas_texto(self):
        datos = extraer_precios_multiples_desde_texto("3 cuotas sin interes de $ 8.333")

        self.assertIn("3 cuotas", datos["cuotas_texto"])
        self.assertEqual(datos["precio_tarjeta_decimal"], Decimal("8333.00"))

    def test_precio_oportunidad_menor_precio_valido(self):
        datos = extraer_precios_multiples_desde_texto("Lista $ 25.000 Tarjeta $ 23.000")

        self.assertEqual(datos["precio_oportunidad_decimal"], Decimal("23000.00"))
        self.assertEqual(datos["tipo_precio_oportunidad"], PrecioFuente.TIPO_PRECIO_TARJETA)

    def test_no_detecta_login_bloqueante_si_hay_productos(self):
        self.assertFalse(detectar_bloqueos_html(self._tiendanube_html(), productos_detectados=True))

    def test_no_toma_menu_como_producto(self):
        preset = obtener_preset_selectores_tiendanube()
        config = type("Config", (), {"dominio_permitido": "ganga.example", **preset})()
        html = '<nav><a href="/cart">Ver carrito</a></nav><div class="js-item-product"><a href="/productos/p" title="Producto real"></a><span>$ 4.000</span></div>'

        productos = extraer_css_productos(html, "https://ganga.example/c", config)

        self.assertEqual(len(productos), 1)
        self.assertEqual(productos[0]["titulo"], "Producto real")

    @patch("oportunidades.services.laboratorio_mapeo_service.requests.get")
    def test_laboratorio_tiendanube_detecta_productos_con_multiprecio(self, get_mock):
        get_mock.return_value = self._response(self._tiendanube_html())

        resultado = analizar_url_laboratorio("https://ganga.example/categoria", preset="tiendanube")

        self.assertEqual(resultado["plataforma_detectada"], "tiendanube")
        self.assertEqual(len(resultado["productos_detectados"]), 1)
        producto = resultado["productos_detectados"][0]
        self.assertEqual(producto["precio_transferencia_decimal"], Decimal("21500.00"))
        self.assertEqual(producto["precio_oportunidad_decimal"], Decimal("21500.00"))
        self.assertTrue(producto["imagen_url"])
