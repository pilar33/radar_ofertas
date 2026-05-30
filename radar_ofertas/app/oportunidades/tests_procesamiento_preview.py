from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase

from oportunidades.models import (
    ConfiguracionExtractorWeb,
    ConectorFuente,
    EjecucionConector,
    FuenteWeb,
    PoliticaExtraccionFuente,
    PrecioFuente,
    ProductoFuente,
    ResultadoExtraccionWeb,
)
from oportunidades.services.headless_diagnostic_service import diagnosticar_requiere_headless, headless_disponible
from oportunidades.services.procesamiento_preview_service import procesar_resultado_preview, procesar_resultados_seleccionados
from oportunidades.services.wizard_fuentes_service import crear_fuente_wizard
from oportunidades.views import estado_operativo_decohome


class ProcesamientoPreviewTests(TestCase):
    def _base(self, permite=True):
        fuente = FuenteWeb.objects.create(nombre="Preview Fuente", url_base="https://example.com/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE)
        PoliticaExtraccionFuente.objects.create(
            fuente=fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO,
            permite_scraping=permite,
            robots_txt_revisado=True,
            terminos_revisados=True,
        )
        conector = ConectorFuente.objects.create(
            fuente_web=fuente,
            nombre="Conector preview",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_revision_manual=False,
            respeta_politica_fuente=True,
        )
        ConfiguracionExtractorWeb.objects.create(
            conector=conector,
            url_inicio="https://example.com/",
            pagina_prueba_url="https://example.com/c",
            dominio_permitido="example.com",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_JSON_LD,
            habilitado=True,
            solo_preview=True,
        )
        ejecucion = EjecucionConector.objects.create(conector=conector)
        resultado = ResultadoExtraccionWeb.objects.create(
            ejecucion=ejecucion,
            titulo="Producto Preview",
            precio_texto="$ 1.200",
            precio_decimal=Decimal("1200.00"),
            url_producto="https://example.com/p",
            seleccionado=True,
        )
        return fuente, conector, ejecucion, resultado

    def test_procesar_resultado_preview_crea_producto_fuente(self):
        _, _, _, resultado = self._base()

        procesado = procesar_resultado_preview(resultado)

        self.assertTrue(procesado["ok"])
        self.assertEqual(ProductoFuente.objects.count(), 1)

    def test_procesar_resultado_preview_no_duplica_por_url(self):
        _, _, _, resultado = self._base()

        procesar_resultado_preview(resultado)
        otro = ResultadoExtraccionWeb.objects.create(
            ejecucion=resultado.ejecucion,
            titulo="Producto Preview",
            precio_decimal=Decimal("1200.00"),
            url_producto="https://example.com/p",
        )
        procesar_resultado_preview(otro)

        self.assertEqual(ProductoFuente.objects.count(), 1)

    def test_procesar_resultado_preview_crea_precio_si_cambia(self):
        _, _, _, resultado = self._base()

        procesar_resultado_preview(resultado)
        otro = ResultadoExtraccionWeb.objects.create(
            ejecucion=resultado.ejecucion,
            titulo="Producto Preview",
            precio_decimal=Decimal("1500.00"),
            url_producto="https://example.com/p",
        )
        procesar_resultado_preview(otro)

        self.assertEqual(PrecioFuente.objects.count(), 2)

    def test_procesar_resultados_seleccionados_limita_20(self):
        _, _, ejecucion, resultado = self._base()
        for i in range(25):
            ResultadoExtraccionWeb.objects.create(
                ejecucion=ejecucion,
                titulo=f"Producto {i}",
                precio_decimal=Decimal("100.00"),
                url_producto=f"https://example.com/p{i}",
                seleccionado=True,
            )
        resultado.seleccionado = True
        resultado.save()

        resumen = procesar_resultados_seleccionados(ejecucion, limite=20)

        self.assertEqual(resumen["procesados"], 20)
        self.assertGreater(resumen["omitidos"], 0)

    def test_no_procesa_si_politica_bloquea(self):
        _, _, _, resultado = self._base(permite=False)

        procesado = procesar_resultado_preview(resultado)

        self.assertFalse(procesado["ok"])
        self.assertEqual(ProductoFuente.objects.count(), 0)

    def test_wizard_crea_fuente_con_politica_desconocida(self):
        fuente, _ = crear_fuente_wizard({"nombre": "Wizard", "url_base": "https://wizard.example", "tipo_fuente": FuenteWeb.TIPO_TIENDA_ONLINE})

        self.assertEqual(fuente.politica_extraccion.semaforo, PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO)

    def test_preparar_fuente_generica_requiere_url(self):
        salida = StringIO()
        with self.assertRaises(CommandError):
            call_command("preparar_fuente_generica", "--nombre", "GangaHome", stdout=salida)

    def test_preparar_fuente_generica_no_duplica(self):
        call_command("preparar_fuente_generica", "--nombre", "GangaHome", "--url-base", "https://ganga.example", "--rubro", "hogar/deco")
        call_command("preparar_fuente_generica", "--nombre", "GangaHome", "--url-base", "https://ganga.example", "--rubro", "hogar/deco")

        self.assertEqual(FuenteWeb.objects.filter(nombre="GangaHome").count(), 1)

    def test_estado_operativo_decohome_muestra_condiciones_faltantes(self):
        request = RequestFactory().get("/fuentes/decohome/estado-operativo/")
        response = estado_operativo_decohome(request)

        self.assertEqual(response.status_code, 200)

    def test_headless_desactivado_por_defecto(self):
        self.assertFalse(headless_disponible()["disponible"])

    def test_diagnostico_js_no_rompe_si_playwright_no_instalado(self):
        _, conector, _, _ = self._base()
        config = conector.configuracion_web

        diagnostico = diagnosticar_requiere_headless(config)

        self.assertFalse(diagnostico["habilitado"])
