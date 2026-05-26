import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from oportunidades.models import (
    ConfiguracionExtractorWeb,
    ConectorFuente,
    FuenteWeb,
    PoliticaExtraccionFuente,
    ProductoFuente,
    RevisionManualFuente,
)
from oportunidades.services.revision_fuentes_service import crear_revision_manual
from oportunidades.services.selector_preview_service import (
    diagnosticar_html_para_extraccion,
    probar_selectores_en_html,
    probar_url_preview,
)


class SelectoresPreviewControladoTests(TestCase):
    def _crear_base(self, robots=True, terminos=True):
        fuente = FuenteWeb.objects.create(
            nombre="Fuente selectores",
            url_base="https://example.com/",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            activa=True,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO,
            permite_scraping=True,
            robots_txt_revisado=robots,
            terminos_revisados=terminos,
        )
        conector = ConectorFuente.objects.create(
            fuente_web=fuente,
            nombre="Scraping controlado",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_revision_manual=False,
            respeta_politica_fuente=True,
        )
        config = ConfiguracionExtractorWeb.objects.create(
            conector=conector,
            pagina_prueba_url="https://example.com/categoria",
            url_inicio="https://example.com/",
            dominio_permitido="example.com",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_CSS_SELECTORS,
            product_card_selector=".product",
            title_selector=".title",
            price_selector=".price",
            url_selector="a",
            image_selector="img",
            max_paginas=1,
            max_productos=10,
            delay_segundos=Decimal("2.00"),
            habilitado=True,
            solo_preview=True,
        )
        return fuente, conector, config

    def _response(self, html):
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/html"}
        response.encoding = "utf-8"
        response.iter_content.return_value = [html.encode("utf-8")]
        return response

    def test_revision_manual_terminos_actualiza_politica(self):
        fuente, _, _ = self._crear_base(terminos=False)

        crear_revision_manual(
            {
                "fuente_web": fuente,
                "tipo_revision": RevisionManualFuente.TIPO_TERMINOS,
                "resultado": RevisionManualFuente.RESULTADO_PERMITE,
                "resumen": "Terminos revisados manualmente.",
                "decision": "Permite revision limitada; no habilita scraping por si sola.",
            },
            aplicar=True,
        )

        fuente.politica_extraccion.refresh_from_db()
        self.assertTrue(fuente.politica_extraccion.terminos_revisados)

    def test_revision_manual_prohibe_pone_fuente_roja(self):
        fuente, _, _ = self._crear_base()

        crear_revision_manual(
            {
                "fuente_web": fuente,
                "tipo_revision": RevisionManualFuente.TIPO_TERMINOS,
                "resultado": RevisionManualFuente.RESULTADO_PROHIBE,
                "resumen": "Prohibe extraccion automatizada.",
            },
            aplicar=True,
        )

        fuente.politica_extraccion.refresh_from_db()
        self.assertEqual(fuente.politica_extraccion.semaforo, PoliticaExtraccionFuente.SEMAFORO_ROJO)
        self.assertFalse(fuente.politica_extraccion.permite_scraping)

    def test_revision_manual_dudoso_no_habilita_scraping(self):
        fuente, _, _ = self._crear_base()
        fuente.politica_extraccion.permite_scraping = False
        fuente.politica_extraccion.save()

        crear_revision_manual(
            {
                "fuente_web": fuente,
                "tipo_revision": RevisionManualFuente.TIPO_TERMINOS,
                "resultado": RevisionManualFuente.RESULTADO_DUDOSO,
                "resumen": "No queda claro.",
            },
            aplicar=True,
        )

        fuente.politica_extraccion.refresh_from_db()
        self.assertFalse(fuente.politica_extraccion.permite_scraping)

    def test_configuracion_selectores_rechaza_dominio_externo(self):
        _, _, config = self._crear_base()
        config.pagina_prueba_url = "https://otro.example.com/categoria"

        with self.assertRaises(Exception):
            config.full_clean()

    def test_configuracion_selectores_requiere_selectores_css(self):
        _, _, config = self._crear_base()
        config.product_card_selector = ""

        with self.assertRaises(Exception):
            config.full_clean()

    def test_probar_selectores_html_detecta_productos(self):
        _, _, config = self._crear_base()
        html = '<div class="product"><a href="/p"><span class="title">Producto</span></a><span class="price">$ 1.200</span><img src="/i.jpg"></div>'

        resultado = probar_selectores_en_html(html, config, "https://example.com/categoria")

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["productos_detectados"], 1)

    def test_probar_selectores_html_sin_productos(self):
        _, _, config = self._crear_base()

        resultado = probar_selectores_en_html("<html></html>", config, "https://example.com/")

        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["productos_detectados"], 0)

    def test_diagnosticar_html_detecta_json_ld(self):
        html = '<script type="application/ld+json">{"@type":"Product","name":"Demo"}</script>'

        diagnostico = diagnosticar_html_para_extraccion(html)

        self.assertTrue(diagnostico["tiene_json_ld"])

    def test_diagnosticar_html_detecta_js_probable(self):
        diagnostico = diagnosticar_html_para_extraccion('<div id="app-root"></div><script>window.__APP__={}</script>')

        self.assertTrue(diagnostico["requiere_js_probable"])

    @patch("oportunidades.services.extractor_web_service.requests.get")
    def test_probar_url_preview_no_procesa_productos(self, requests_get):
        _, _, config = self._crear_base()
        html = '<div class="product"><a href="/p"><span class="title">Producto</span></a><span class="price">$ 1.200</span></div>'
        requests_get.return_value = self._response(html)

        resultado = probar_url_preview(config)

        self.assertEqual(resultado["productos_detectados"], 1)
        self.assertEqual(ProductoFuente.objects.count(), 0)

    def test_preview_bloqueado_si_terminos_no_revisados(self):
        _, _, config = self._crear_base(terminos=False)

        resultado = probar_url_preview(config)

        self.assertFalse(resultado["ok"])
        self.assertIn("terminos_revisados", resultado["errores"][0])

    def test_preview_bloqueado_si_robots_no_revisado(self):
        _, _, config = self._crear_base(robots=False)

        resultado = probar_url_preview(config)

        self.assertFalse(resultado["ok"])
        self.assertIn("robots_txt_revisado", resultado["errores"][0])

    def test_configurar_selectores_decohome_no_inventa_selectores(self):
        call_command("configurar_selectores_decohome")

        config = ConfiguracionExtractorWeb.objects.get(conector__fuente_web__nombre="Deco Home")

        self.assertFalse(config.product_card_selector)
        self.assertFalse(config.title_selector)
        self.assertFalse(config.price_selector)
