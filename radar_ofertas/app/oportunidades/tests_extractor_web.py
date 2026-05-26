import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from oportunidades.management.commands.configurar_extractor_decohome import configurar_extractor_decohome
from oportunidades.models import (
    ConfiguracionExtractorWeb,
    ConectorFuente,
    EjecucionConector,
    FuenteWeb,
    PoliticaExtraccionFuente,
    ProductoFuente,
    ResultadoExtraccionWeb,
)
from oportunidades.services.extractor_web_service import (
    extraer_css_productos,
    extraer_json_ld_productos,
    extraer_productos_preview,
    parsear_precio_web,
    procesar_resultado_a_producto,
    validar_ejecucion_extractor,
)


class ExtractorWebControladoTests(TestCase):
    def _crear_conector(self, semaforo=PoliticaExtraccionFuente.SEMAFORO_VERDE, **politica_kwargs):
        fuente = FuenteWeb.objects.create(
            nombre=f"Fuente {semaforo}",
            url_base="https://example.com/",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            activa=True,
        )
        defaults = {
            "semaforo": semaforo,
            "metodo_preferido": PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO,
            "permite_scraping": True,
            "robots_txt_revisado": True,
            "terminos_revisados": True,
            "requiere_login": False,
            "tiene_captcha": False,
        }
        defaults.update(politica_kwargs)
        PoliticaExtraccionFuente.objects.create(fuente=fuente, **defaults)
        conector = ConectorFuente.objects.create(
            fuente_web=fuente,
            nombre="Extractor controlado",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_revision_manual=False,
            respeta_politica_fuente=True,
        )
        config = ConfiguracionExtractorWeb.objects.create(
            conector=conector,
            url_inicio="https://example.com/categoria",
            dominio_permitido="example.com",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_JSON_LD,
            max_paginas=1,
            max_productos=10,
            delay_segundos=Decimal("2.00"),
            habilitado=True,
            solo_preview=True,
        )
        return fuente, conector, config

    def _response(self, html, status=200, content_type="text/html"):
        response = Mock()
        response.status_code = status
        response.headers = {"Content-Type": content_type}
        response.encoding = "utf-8"
        response.iter_content.return_value = [html.encode("utf-8")]
        return response

    def test_configuracion_extractor_limita_max_paginas(self):
        _, _, config = self._crear_conector()
        config.max_paginas = 4

        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_configuracion_extractor_limita_max_productos(self):
        _, _, config = self._crear_conector()
        config.max_productos = 51

        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_configuracion_extractor_delay_minimo(self):
        _, _, config = self._crear_conector()
        config.delay_segundos = Decimal("1.00")

        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_extractor_bloquea_fuente_roja(self):
        _, conector, _ = self._crear_conector(semaforo=PoliticaExtraccionFuente.SEMAFORO_ROJO)

        self.assertEqual(validar_ejecucion_extractor(conector)["nivel"], "bloqueado")

    def test_extractor_bloquea_semaforo_desconocido(self):
        _, conector, _ = self._crear_conector(semaforo=PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO)

        self.assertEqual(validar_ejecucion_extractor(conector)["nivel"], "bloqueado")

    def test_extractor_bloquea_si_robots_no_revisado(self):
        _, conector, _ = self._crear_conector(robots_txt_revisado=False)

        self.assertIn("robots_txt_revisado", validar_ejecucion_extractor(conector)["mensaje"])

    def test_extractor_bloquea_si_terminos_no_revisados(self):
        _, conector, _ = self._crear_conector(terminos_revisados=False)

        self.assertIn("terminos_revisados", validar_ejecucion_extractor(conector)["mensaje"])

    def test_extractor_bloquea_si_permite_scraping_false(self):
        _, conector, _ = self._crear_conector(permite_scraping=False)

        self.assertFalse(validar_ejecucion_extractor(conector)["valido"])

    def test_extractor_bloquea_captcha(self):
        _, conector, _ = self._crear_conector(tiene_captcha=True)

        self.assertIn("captcha", validar_ejecucion_extractor(conector)["mensaje"])

    def test_parsear_precio_web_argentino(self):
        self.assertEqual(parsear_precio_web("$ 12.345,50")[0], Decimal("12345.50"))
        self.assertEqual(parsear_precio_web("ARS 12.345")[0], Decimal("12345.00"))

    def test_extraer_json_ld_productos_mock(self):
        _, _, config = self._crear_conector()
        html = """
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Product","name":"Producto JSON","description":"Demo","image":"/img.jpg","url":"/p","offers":{"price":"1234.50"}}
        </script>
        """

        productos = extraer_json_ld_productos(html, "https://example.com/categoria", config)

        self.assertEqual(productos[0]["titulo"], "Producto JSON")
        self.assertEqual(productos[0]["url_producto"], "https://example.com/p")

    def test_extraer_css_productos_mock(self):
        _, _, config = self._crear_conector()
        config.modo_extraccion = ConfiguracionExtractorWeb.MODO_CSS_SELECTORS
        config.product_card_selector = ".product"
        config.title_selector = ".title"
        config.price_selector = ".price"
        config.url_selector = "a"
        config.image_selector = "img"
        html = '<div class="product"><a href="/p"><span class="title">Producto CSS</span></a><span class="price">$ 2.500</span><img src="/p.jpg"></div>'

        productos = extraer_css_productos(html, "https://example.com/categoria", config)

        self.assertEqual(productos[0]["titulo"], "Producto CSS")
        self.assertEqual(productos[0]["imagen_url"], "https://example.com/p.jpg")

    @patch("oportunidades.services.extractor_web_service.requests.get")
    def test_preview_no_crea_producto_fuente(self, requests_get):
        _, conector, _ = self._crear_conector()
        data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Producto Preview",
            "url": "/preview",
            "offers": {"price": "1000"},
        }
        html = f'<script type="application/ld+json">{json.dumps(data)}</script>'
        requests_get.return_value = self._response(html)

        ejecucion = extraer_productos_preview(conector)

        self.assertEqual(ejecucion.productos_detectados, 1)
        self.assertEqual(ResultadoExtraccionWeb.objects.count(), 1)
        self.assertEqual(ProductoFuente.objects.count(), 0)

    def test_procesar_resultado_crea_producto_precio_con_validacion(self):
        _, conector, _ = self._crear_conector()
        ejecucion = EjecucionConector.objects.create(conector=conector)
        resultado = ResultadoExtraccionWeb.objects.create(
            ejecucion=ejecucion,
            titulo="Producto Procesado",
            precio_texto="$ 1.500",
            precio_decimal=Decimal("1500.00"),
            url_producto="https://example.com/procesado",
        )

        procesar_resultado_a_producto(resultado, conector)

        self.assertEqual(ProductoFuente.objects.count(), 1)
        resultado.refresh_from_db()
        self.assertEqual(resultado.estado, ResultadoExtraccionWeb.ESTADO_PROCESADO)

    def test_configurar_extractor_decohome_no_activa_por_defecto(self):
        call_command("preparar_decohome")

        config, _ = configurar_extractor_decohome()

        self.assertFalse(config.habilitado)
        self.assertTrue(config.solo_preview)

    def test_preview_decohome_bloqueado_si_politica_incompleta(self):
        config, _ = configurar_extractor_decohome()

        ejecucion = extraer_productos_preview(config.conector)

        self.assertEqual(ejecucion.errores, 1)
        self.assertIn("El conector no esta activo", ejecucion.mensaje)
