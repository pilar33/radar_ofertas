from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from oportunidades.models import (
    ConfiguracionExtractorWeb,
    ConectorFuente,
    EjecucionConector,
    FuenteWeb,
    PoliticaExtraccionFuente,
    ResultadoExtraccionWeb,
)
from oportunidades.services.estado_fuente_service import evaluar_estado_operativo_fuente
from oportunidades.services.headless_diagnostic_service import comparar_html_requests_vs_headless, headless_disponible
from oportunidades.services.ranking_preview_service import calcular_score_resultado_preview


class Etapa310Tests(TestCase):
    def _fuente(self, semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO, habilitada=True, requiere_js=False):
        fuente = FuenteWeb.objects.create(nombre="Fuente 310", url_base="https://example.com/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE)
        PoliticaExtraccionFuente.objects.create(
            fuente=fuente,
            semaforo=semaforo,
            metodo_preferido=PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO,
            permite_scraping=habilitada,
            robots_txt_revisado=habilitada,
            terminos_revisados=habilitada,
        )
        conector = ConectorFuente.objects.create(
            fuente_web=fuente,
            nombre="Conector 310",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO if habilitada else ConectorFuente.ESTADO_BORRADOR,
            requiere_revision_manual=not habilitada,
            respeta_politica_fuente=habilitada,
        )
        config = ConfiguracionExtractorWeb.objects.create(
            conector=conector,
            url_inicio="https://example.com/",
            pagina_prueba_url="https://example.com/c",
            dominio_permitido="example.com",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_JSON_LD,
            habilitado=habilitada,
            solo_preview=True,
            requiere_js_detectado=requiere_js,
        )
        ejecucion = EjecucionConector.objects.create(conector=conector)
        return fuente, conector, config, ejecucion

    def test_estado_fuente_desconocida_falta_auditoria(self):
        fuente, _, _, _ = self._fuente(semaforo=PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO, habilitada=False)

        estado = evaluar_estado_operativo_fuente(fuente)

        self.assertIn("semaforo desconocido", estado["faltantes"])

    def test_estado_fuente_lista_para_preview(self):
        fuente, _, _, _ = self._fuente()

        estado = evaluar_estado_operativo_fuente(fuente)

        self.assertTrue(estado["puede_preview"])

    def test_estado_fuente_requiere_js(self):
        fuente, _, _, _ = self._fuente(requiere_js=True)

        estado = evaluar_estado_operativo_fuente(fuente)

        self.assertTrue(estado["requiere_js"])

    def test_ranking_preview_score_alto_con_datos_completos(self):
        _, _, _, ejecucion = self._fuente()
        resultado = ResultadoExtraccionWeb.objects.create(
            ejecucion=ejecucion,
            titulo="Oferta organizador cocina",
            precio_decimal=Decimal("1200.00"),
            url_producto="https://example.com/p",
            imagen_url="https://example.com/p.jpg",
            descripcion="Producto en descuento",
        )

        score = calcular_score_resultado_preview(resultado)

        self.assertGreaterEqual(score["score"], 70)

    def test_ranking_preview_score_bajo_sin_precio(self):
        _, _, _, ejecucion = self._fuente()
        resultado = ResultadoExtraccionWeb.objects.create(ejecucion=ejecucion, titulo="Producto sin precio")

        score = calcular_score_resultado_preview(resultado)

        self.assertLess(score["score"], 50)

    def test_preparar_gangahome_requiere_url(self):
        with self.assertRaises(CommandError):
            call_command("preparar_gangahome", stdout=StringIO())

    def test_preparar_gangahome_crea_fuente(self):
        call_command("preparar_gangahome", "--url-base", "https://ganga.example/", stdout=StringIO())

        self.assertTrue(FuenteWeb.objects.filter(nombre="GangaHome").exists())

    def test_headless_deshabilitado_por_defecto(self):
        self.assertFalse(headless_disponible()["disponible"])

    @patch("oportunidades.services.headless_diagnostic_service.hacer_request_extractor")
    def test_diagnostico_headless_no_procesa_productos(self, request_mock):
        _, _, config, _ = self._fuente()
        request_mock.return_value = {"ok": True, "text": "<html></html>", "error": ""}

        comparacion = comparar_html_requests_vs_headless(config)

        self.assertEqual(comparacion["estado"], "headless deshabilitado")
        self.assertEqual(ResultadoExtraccionWeb.objects.count(), 0)
