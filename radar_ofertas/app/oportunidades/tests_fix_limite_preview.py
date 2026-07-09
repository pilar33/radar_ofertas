from decimal import Decimal

from django.test import TestCase

from oportunidades.forms import ConfiguracionExtractorWebForm, LaboratorioMapeoForm
from oportunidades.models import ConfiguracionExtractorWeb, ConectorFuente, FuenteWeb, PoliticaExtraccionFuente
from oportunidades.services.extractor_web_service import validar_ejecucion_extractor
from oportunidades.services.preview_controlado_service import reparar_extractor_gangahome


class FixLimitePreviewTests(TestCase):
    def setUp(self):
        self.fuente = FuenteWeb.objects.create(
            nombre="Tienda prueba",
            url_base="https://tienda.example/",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
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
            nombre="Extractor prueba",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_revision_manual=False,
            respeta_politica_fuente=True,
        )

    def _form_data(self, max_productos):
        return {
            "url_inicio": "https://tienda.example/",
            "url_categoria": "https://tienda.example/categoria/",
            "pagina_prueba_url": "https://tienda.example/categoria/",
            "dominio_permitido": "tienda.example",
            "modo_extraccion": ConfiguracionExtractorWeb.MODO_MIXTO,
            "max_paginas": 1,
            "max_productos": max_productos,
            "delay_segundos": "2.00",
            "timeout_segundos": 20,
            "habilitado": "on",
            "solo_preview": "on",
        }

    def test_configuracion_extractor_form_acepta_100_productos(self):
        form = ConfiguracionExtractorWebForm(data=self._form_data(100))
        self.assertTrue(form.is_valid(), form.errors)

    def test_configuracion_extractor_form_rechaza_mas_de_100_productos(self):
        form = ConfiguracionExtractorWebForm(data=self._form_data(101))
        self.assertFalse(form.is_valid())
        self.assertIn("100", str(form.errors))

    def test_laboratorio_mapeo_form_permite_limite_100(self):
        form = LaboratorioMapeoForm(data={"url": "https://tienda.example/", "modo": LaboratorioMapeoForm.MODO_AUTO, "limite": 100, "solo_preview": "on"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_validar_ejecucion_extractor_acepta_100(self):
        ConfiguracionExtractorWeb.objects.create(
            conector=self.conector,
            url_inicio="https://tienda.example/",
            url_categoria="https://tienda.example/categoria/",
            pagina_prueba_url="https://tienda.example/categoria/",
            dominio_permitido="tienda.example",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_MIXTO,
            max_paginas=1,
            max_productos=100,
            delay_segundos=Decimal("2.00"),
            habilitado=True,
            solo_preview=True,
        )
        self.assertTrue(validar_ejecucion_extractor(self.conector)["valido"])

    def test_reparar_extractor_gangahome_deja_max_productos_100(self):
        _, _, extractor = reparar_extractor_gangahome()
        self.assertEqual(extractor.max_productos, 100)
