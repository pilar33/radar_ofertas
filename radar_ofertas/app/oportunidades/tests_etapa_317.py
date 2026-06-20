from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import Client, TestCase

from oportunidades.models import (
    CategoriaInteres, ConfiguracionExtractorWeb, ConectorFuente, EjecucionConector, FuenteWeb,
    PoliticaExtraccionFuente, PrecioFuente, ProductoCanonico, ProductoFuente,
    ResultadoExtraccionWeb, SenalDemandaProducto,
)
from oportunidades.services.dataset_export_service import exportar_dataset_productos_csv
from oportunidades.services.demanda_service import (
    calcular_score_demanda, crear_o_actualizar_senal_demanda, extraer_senales_demanda_desde_texto,
)
from oportunidades.services.procesamiento_preview_service import procesar_resultado_preview
from oportunidades.services.ranking_comercial_service import calcular_score_comercial_producto_fuente


class Etapa317DemandaTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(nombre="Cocina", palabra_clave="cocina")
        self.fuente = FuenteWeb.objects.create(nombre="Tienda demanda", url_base="https://demanda.example/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE)
        self.canonico = ProductoCanonico.objects.create(nombre_normalizado="frasco vidrio", categoria=self.categoria)
        self.producto = ProductoFuente.objects.create(
            producto_canonico=self.canonico, fuente_web=self.fuente, titulo_original="Frasco vidrio",
            url_producto="https://demanda.example/frasco", condicion="nuevo", imagen_url="https://demanda.example/frasco.jpg",
        )
        PrecioFuente.objects.create(
            producto_fuente=self.producto, precio=Decimal("8000"), precio_lista=Decimal("10000"),
            precio_transferencia=Decimal("8000"), precio_oportunidad=Decimal("8000"),
            tipo_precio_oportunidad=PrecioFuente.TIPO_PRECIO_TRANSFERENCIA, origen_dato=PrecioFuente.ORIGEN_MANUAL,
        )

    def test_extraer_vendidos_visibles(self):
        datos = extraer_senales_demanda_desde_texto("+100 vendidos")
        self.assertEqual(datos["cantidad_vendida_visible"], 100)

    def test_extraer_mas_vendido(self):
        self.assertTrue(extraer_senales_demanda_desde_texto("Más vendido")["etiqueta_mas_vendido"])

    def test_extraer_resenas(self):
        self.assertEqual(extraer_senales_demanda_desde_texto("230 opiniones")["cantidad_resenas"], 230)

    def test_extraer_preguntas(self):
        self.assertEqual(extraer_senales_demanda_desde_texto("15 preguntas")["cantidad_preguntas"], 15)

    def test_extraer_stock_visible(self):
        self.assertEqual(extraer_senales_demanda_desde_texto("Quedan 3")["stock_visible"], 3)

    def test_extraer_agotado(self):
        datos = extraer_senales_demanda_desde_texto("Producto agotado")
        self.assertEqual(datos["stock_visible"], 0)
        self.assertIn("agotado", datos["texto_stock"].lower())

    def test_score_demanda_alta_con_vendidos_resenas(self):
        resultado = calcular_score_demanda({"cantidad_vendida_visible": 100, "cantidad_resenas": 230})
        self.assertEqual(resultado["nivel"], ProductoFuente.DEMANDA_ALTA)

    def test_score_demanda_media_con_destacado(self):
        resultado = calcular_score_demanda({"etiqueta_destacado": True})
        self.assertEqual(resultado["nivel"], ProductoFuente.DEMANDA_MEDIA)

    def test_score_demanda_baja_sin_senales(self):
        resultado = calcular_score_demanda({"texto_stock": "Sin stock"})
        self.assertLess(resultado["score"], 40)

    def test_score_demanda_no_inventa_ventas(self):
        datos = extraer_senales_demanda_desde_texto("Destacado y tendencia")
        self.assertEqual(datos["cantidad_vendida_visible"], 0)

    def _preview(self):
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente, semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO, permite_scraping=True,
            robots_txt_revisado=True, terminos_revisados=True,
        )
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente, nombre="Preview demanda", tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO, requiere_revision_manual=False, respeta_politica_fuente=True,
        )
        ConfiguracionExtractorWeb.objects.create(
            conector=conector, url_inicio=self.fuente.url_base, pagina_prueba_url=self.fuente.url_base,
            dominio_permitido="demanda.example", habilitado=True, solo_preview=True,
        )
        ejecucion = EjecucionConector.objects.create(conector=conector)
        return ResultadoExtraccionWeb.objects.create(
            ejecucion=ejecucion, titulo="Producto nuevo demanda", precio_decimal=Decimal("1200"),
            precio_oportunidad_decimal=Decimal("1200"), url_producto="https://demanda.example/nuevo",
            texto_demanda_detectado="Más vendido 100 vendidos 20 reseñas",
        )

    def test_procesar_preview_crea_senal_demanda(self):
        resultado = self._preview()
        procesado = procesar_resultado_preview(resultado)
        self.assertTrue(procesado["ok"])
        self.assertTrue(procesado["producto_fuente"].senales_demanda.exists())

    def test_recalcular_demanda_command(self):
        salida = StringIO()
        call_command("recalcular_demanda", "--producto-fuente-id", self.producto.pk, stdout=salida)
        self.assertTrue(self.producto.senales_demanda.exists())
        self.assertIn("Demanda recalculada", salida.getvalue())

    def test_ranking_comercial_considera_demanda(self):
        base = calcular_score_comercial_producto_fuente(self.producto, guardar=False)["score"]
        crear_o_actualizar_senal_demanda(self.producto, {"cantidad_vendida_visible": 200, "cantidad_resenas": 300})
        self.producto.refresh_from_db()
        con_demanda = calcular_score_comercial_producto_fuente(self.producto, guardar=False)["score"]
        self.assertGreater(con_demanda, base)

    def test_demanda_dashboard_carga(self):
        self.assertEqual(Client(HTTP_HOST="localhost").get("/demanda/dashboard/").status_code, 200)

    def test_demanda_productos_carga(self):
        self.assertEqual(Client(HTTP_HOST="localhost").get("/demanda/productos/").status_code, 200)

    def test_demanda_detalle_carga(self):
        response = Client(HTTP_HOST="localhost").get(f"/demanda/productos/{self.producto.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_editar_senales_manual(self):
        response = Client(HTTP_HOST="localhost").post(
            f"/demanda/productos/{self.producto.pk}/editar-senales/",
            {"cantidad_vendida_visible": 10, "cantidad_resenas": 5, "cantidad_preguntas": 1, "calificacion": "4.50", "stock_visible": 3},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.producto.senales_demanda.first().origen_dato, SenalDemandaProducto.ORIGEN_MANUAL)

    def test_menu_contiene_flujo_por_proceso(self):
        response = Client(HTTP_HOST="localhost").get("/demanda/dashboard/")
        self.assertContains(response, "1. Fuentes")
        self.assertContains(response, "5. Análisis comercial")

    def test_menu_contiene_demanda(self):
        self.assertContains(Client(HTTP_HOST="localhost").get("/demanda/dashboard/"), "Demanda estimada")

    def test_menu_contiene_dataset_backup(self):
        response = Client(HTTP_HOST="localhost").get("/demanda/dashboard/")
        self.assertContains(response, "Dataset / Exportar")
        self.assertContains(response, "Backup")

    def test_export_dataset_incluye_demanda(self):
        cabecera = exportar_dataset_productos_csv().getvalue().splitlines()[0]
        self.assertIn("score_demanda_actual", cabecera)
        self.assertIn("cantidad_vendida_visible", cabecera)

    def test_manual_operativo_incluye_demanda(self):
        manual = Path(__file__).resolve().parents[1] / "docs" / "manual_operativo_radar.md"
        self.assertIn("Demanda estimada y señales de venta", manual.read_text(encoding="utf-8"))

    def test_manual_operativo_incluye_habilitar_extractor(self):
        manual = Path(__file__).resolve().parents[1] / "docs" / "manual_operativo_radar.md"
        self.assertIn("Habilitar manualmente un extractor guardado", manual.read_text(encoding="utf-8"))
