from django.test import TestCase

from oportunidades.models import ConfiguracionExtractorWeb, ConectorFuente, FuenteWeb, PoliticaExtraccionFuente
from oportunidades.services.wizard_fuentes_service import crear_fuente_preview_rapida


class FuenteRapidaPreviewTests(TestCase):
    def test_crear_fuente_preview_rapida_habilita_flujo(self):
        fuente, conector, extractor, creada, _, plataforma = crear_fuente_preview_rapida(
            {
                "nombre": "Ganga Home",
                "url_base": "https://www.gangahome.com.ar/",
                "url_categoria": "https://www.gangahome.com.ar/cocina/",
                "rubro_principal": "hogar/deco",
                "plataforma": "tiendanube",
            }
        )

        self.assertTrue(creada)
        self.assertEqual(plataforma, "tiendanube")
        self.assertEqual(fuente.tipo_fuente, FuenteWeb.TIPO_TIENDA_ONLINE)
        self.assertEqual(fuente.politica_extraccion.semaforo, PoliticaExtraccionFuente.SEMAFORO_AMARILLO)
        self.assertTrue(fuente.politica_extraccion.permite_scraping)
        self.assertTrue(fuente.politica_extraccion.robots_txt_revisado)
        self.assertTrue(fuente.politica_extraccion.terminos_revisados)
        self.assertEqual(conector.estado, ConectorFuente.ESTADO_ACTIVO)
        self.assertFalse(conector.requiere_revision_manual)
        self.assertTrue(conector.respeta_politica_fuente)
        self.assertEqual(extractor.modo_extraccion, ConfiguracionExtractorWeb.MODO_MIXTO)
        self.assertTrue(extractor.habilitado)
        self.assertTrue(extractor.solo_preview)
        self.assertIn("js-item-product", extractor.product_card_selector)
