from decimal import Decimal

from django.core.management import call_command
from django.test import Client, TestCase

from oportunidades.forms import ConfiguracionExtractorWebForm
from oportunidades.models import ConfiguracionExtractorWeb, ConectorFuente, FuenteWeb, PoliticaExtraccionFuente, ResultadoExtraccionWeb
from oportunidades.services.dominios_service import normalizar_dominio, url_pertenece_a_dominio


class FixDominioExtractorTests(TestCase):
    def crear_extractor(self, dominio="www.gangahome.com.ar"):
        fuente = FuenteWeb.objects.create(
            nombre="Ganga Home",
            url_base="https://gangahome.example",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            activa=True,
        )
        PoliticaExtraccionFuente.objects.create(fuente=fuente)
        conector = ConectorFuente.objects.create(
            fuente_web=fuente,
            nombre="Ganga Home - Extractor laboratorio",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_BORRADOR,
            requiere_revision_manual=True,
            respeta_politica_fuente=False,
        )
        extractor = ConfiguracionExtractorWeb.objects.create(
            conector=conector,
            url_inicio="https://gangahome.example",
            url_categoria="https://www.gangahome.com.ar/cocina/",
            pagina_prueba_url="https://www.gangahome.com.ar/cocina/",
            dominio_permitido=dominio,
            modo_extraccion=ConfiguracionExtractorWeb.MODO_MIXTO,
            max_paginas=1,
            max_productos=10,
            delay_segundos=Decimal("2.00"),
            habilitado=False,
            solo_preview=True,
        )
        return fuente, conector, extractor

    def test_normalizar_dominio_con_www(self):
        self.assertEqual(normalizar_dominio("https://www.gangahome.com.ar/cocina/"), "gangahome.com.ar")

    def test_normalizar_dominio_sin_www(self):
        self.assertEqual(normalizar_dominio("gangahome.com.ar"), "gangahome.com.ar")

    def test_url_pertenece_a_dominio_acepta_www_equivalente(self):
        self.assertTrue(url_pertenece_a_dominio("https://www.gangahome.com.ar/cocina/", "gangahome.com.ar"))
        self.assertTrue(url_pertenece_a_dominio("https://gangahome.com.ar/cocina/", "www.gangahome.com.ar"))

    def test_url_pertenece_a_dominio_rechaza_externo(self):
        self.assertFalse(url_pertenece_a_dominio("https://otra-tienda.com/cocina/", "gangahome.com.ar"))

    def test_configuracion_extractor_valida_gangahome_con_www(self):
        data = {
            "pagina_prueba_url": "https://www.gangahome.com.ar/cocina/",
            "url_inicio": "https://www.gangahome.com.ar/",
            "url_categoria": "https://www.gangahome.com.ar/cocina/",
            "dominio_permitido": "www.gangahome.com.ar",
            "modo_extraccion": ConfiguracionExtractorWeb.MODO_MIXTO,
            "max_paginas": 1,
            "max_productos": 10,
            "delay_segundos": "2.00",
            "timeout_segundos": 15,
            "solo_preview": "on",
        }
        form = ConfiguracionExtractorWebForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["dominio_permitido"], "gangahome.com.ar")

    def test_configuracion_extractor_valida_gangahome_sin_www(self):
        data = {
            "pagina_prueba_url": "https://www.gangahome.com.ar/cocina/",
            "url_inicio": "https://gangahome.com.ar/",
            "url_categoria": "https://www.gangahome.com.ar/cocina/",
            "dominio_permitido": "gangahome.com.ar",
            "modo_extraccion": ConfiguracionExtractorWeb.MODO_MIXTO,
            "max_paginas": 1,
            "max_productos": 10,
            "delay_segundos": "2.00",
            "timeout_segundos": 15,
            "solo_preview": "on",
        }
        form = ConfiguracionExtractorWebForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)

    def test_reparar_extractor_gangahome_corrige_placeholder(self):
        self.crear_extractor()

        call_command("reparar_extractor_gangahome")
        extractor = ConfiguracionExtractorWeb.objects.select_related("conector__fuente_web").get()

        self.assertEqual(extractor.url_inicio, "https://www.gangahome.com.ar/")
        self.assertEqual(extractor.url_categoria, "https://www.gangahome.com.ar/cocina/")
        self.assertEqual(extractor.pagina_prueba_url, "https://www.gangahome.com.ar/cocina/")
        self.assertEqual(extractor.dominio_permitido, "gangahome.com.ar")
        self.assertTrue(extractor.habilitado)
        self.assertTrue(extractor.solo_preview)
        self.assertEqual(extractor.conector.estado, ConectorFuente.ESTADO_ACTIVO)

    def test_habilitar_preview_controlado_no_procesa_productos(self):
        _fuente, _conector, extractor = self.crear_extractor(dominio="gangahome.com.ar")
        response = Client(HTTP_HOST="localhost").post(
            f"/extractores/{extractor.pk}/habilitar-preview-controlado/",
            follow=True,
        )
        extractor.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(extractor.habilitado)
        self.assertTrue(extractor.solo_preview)
        self.assertEqual(ResultadoExtraccionWeb.objects.count(), 0)
