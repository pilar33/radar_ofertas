from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from oportunidades.models import (
    FuenteWeb,
    PoliticaExtraccionFuente,
    ResultadoLaboratorioMapeo,
    SesionLaboratorioMapeo,
)
from oportunidades.services.laboratorio_mapeo_service import (
    analizar_url_laboratorio,
    crear_sesion_laboratorio,
    guardar_laboratorio_como_extractor,
    procesar_resultados_laboratorio,
    probar_selectores_laboratorio,
    sugerir_selectores,
)


class LaboratorioMapeoTests(TestCase):
    def _response(self, html, status=200, content_type="text/html"):
        response = Mock()
        response.status_code = status
        response.headers = {"Content-Type": content_type}
        response.encoding = "utf-8"
        response.iter_content.return_value = [html.encode("utf-8")]
        return response

    def _fuente(self, habilitada=True):
        fuente = FuenteWeb.objects.create(
            nombre="Fuente Lab",
            url_base="https://example.com/",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            rubro_principal="hogar",
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO if habilitada else PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO,
            permite_scraping=habilitada,
            robots_txt_revisado=habilitada,
            terminos_revisados=habilitada,
        )
        return fuente

    @patch("oportunidades.services.laboratorio_mapeo_service.requests.get")
    def test_laboratorio_analiza_html_con_json_ld(self, get_mock):
        html = """
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Product","name":"Producto JSON","image":"/a.jpg","url":"/p","offers":{"price":"1234.50"}}
        </script>
        """
        get_mock.return_value = self._response(html)

        resultado = analizar_url_laboratorio("https://example.com/c")

        self.assertTrue(resultado["tiene_json_ld"])
        self.assertEqual(resultado["productos_detectados"][0]["titulo"], "Producto JSON")

    @patch("oportunidades.services.laboratorio_mapeo_service.requests.get")
    def test_laboratorio_analiza_html_con_tarjetas_css(self, get_mock):
        html = '<div class="product-card"><a href="/p"><h2>Producto CSS</h2></a><span class="price">$ 2.500</span><img src="/p.jpg"></div>'
        get_mock.return_value = self._response(html)

        resultado = analizar_url_laboratorio("https://example.com/c", modo="auto")

        self.assertEqual(resultado["productos_detectados"][0]["titulo"], "Producto CSS")

    @patch("oportunidades.services.laboratorio_mapeo_service.requests.get")
    def test_laboratorio_detecta_js_probable(self, get_mock):
        get_mock.return_value = self._response('<div id="app-root"></div><script>window.__APP={}</script>')

        resultado = analizar_url_laboratorio("https://example.com/c")

        self.assertTrue(resultado["requiere_js_probable"])

    @patch("oportunidades.services.laboratorio_mapeo_service.requests.get")
    def test_laboratorio_detecta_bloqueo_captcha(self, get_mock):
        get_mock.return_value = self._response("<html>captcha challenge</html>")

        resultado = analizar_url_laboratorio("https://example.com/c")

        self.assertIn("captcha", resultado["bloqueos_detectados"])

    def test_sugerir_selectores_devuelve_selectores(self):
        html = '<div class="product-card"><h2>Producto</h2><span class="price">$ 100</span></div>'

        selectores = sugerir_selectores(html)

        self.assertEqual(selectores["product_card_selector"], ".product-card")

    def test_ajustar_selectores_detecta_productos(self):
        html = '<div class="product-card"><a href="/p"><h2>Producto</h2></a><span class="price">$ 100</span></div>'
        selectores = {
            "product_card_selector": ".product-card",
            "title_selector": "h2",
            "price_selector": ".price",
            "url_selector": "a",
        }

        resultado = probar_selectores_laboratorio(html, "https://example.com/c", selectores)

        self.assertTrue(resultado["ok"])

    @patch("oportunidades.services.laboratorio_mapeo_service.requests.get")
    def test_guardar_como_extractor_crea_configuracion(self, get_mock):
        fuente = self._fuente()
        get_mock.return_value = self._response('<div class="product-card"><h2>Producto</h2><span class="price">$ 100</span></div>')
        analisis = analizar_url_laboratorio("https://example.com/c")
        sesion = crear_sesion_laboratorio(analisis, fuente)

        extractor = guardar_laboratorio_como_extractor(sesion, fuente_web=fuente)

        self.assertEqual(extractor.conector.fuente_web, fuente)
        self.assertTrue(extractor.habilitado)

    @patch("oportunidades.services.laboratorio_mapeo_service.requests.get")
    def test_guardar_como_extractor_deshabilitado_si_politica_desconocida(self, get_mock):
        fuente = self._fuente(habilitada=False)
        get_mock.return_value = self._response('<div class="product-card"><h2>Producto</h2><span class="price">$ 100</span></div>')
        sesion = crear_sesion_laboratorio(analizar_url_laboratorio("https://example.com/c"), fuente)

        extractor = guardar_laboratorio_como_extractor(sesion, fuente_web=fuente)

        self.assertFalse(extractor.habilitado)

    def test_procesar_seleccionados_crea_producto_fuente(self):
        fuente = self._fuente()
        sesion = SesionLaboratorioMapeo.objects.create(url="https://example.com/c", fuente_web=fuente)
        ResultadoLaboratorioMapeo.objects.create(
            sesion=sesion,
            titulo="Producto Lab",
            precio_decimal=Decimal("100.00"),
            url_producto="https://example.com/p",
            seleccionado=True,
        )

        resumen = procesar_resultados_laboratorio(sesion)

        self.assertTrue(resumen["ok"])
        self.assertEqual(resumen["procesados"], 1)

    def test_procesar_seleccionados_limita_10(self):
        fuente = self._fuente()
        sesion = SesionLaboratorioMapeo.objects.create(url="https://example.com/c", fuente_web=fuente)
        for i in range(12):
            ResultadoLaboratorioMapeo.objects.create(
                sesion=sesion,
                titulo=f"Producto {i}",
                precio_decimal=Decimal("100.00"),
                url_producto=f"https://example.com/p{i}",
                seleccionado=True,
            )

        resumen = procesar_resultados_laboratorio(sesion, limite=20)

        self.assertEqual(resumen["procesados"], 10)

    def test_no_procesa_sin_fuente(self):
        sesion = SesionLaboratorioMapeo.objects.create(url="https://example.com/c")

        resumen = procesar_resultados_laboratorio(sesion)

        self.assertFalse(resumen["ok"])

    def test_no_procesa_si_politica_bloquea(self):
        fuente = self._fuente(habilitada=False)
        sesion = SesionLaboratorioMapeo.objects.create(url="https://example.com/c", fuente_web=fuente)

        resumen = procesar_resultados_laboratorio(sesion)

        self.assertFalse(resumen["ok"])

    @patch("oportunidades.services.laboratorio_mapeo_service.requests.get")
    def test_laboratorio_no_hace_scraping_masivo(self, get_mock):
        get_mock.return_value = self._response("<html></html>")

        analizar_url_laboratorio("https://example.com/c")

        self.assertEqual(get_mock.call_count, 1)
