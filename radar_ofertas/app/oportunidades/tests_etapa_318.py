import csv
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase

from oportunidades.models import (
    CategoriaInteres, ConfiguracionExtractorWeb, ConectorFuente, DetalleLoteCaptura, FuenteWeb,
    ImportacionProductos, LoteCaptura, PoliticaExtraccionFuente, PrecioFuente, Producto,
    ProductoCanonico, ProductoFuente, ResultadoExtraccionWeb, ResultadoLaboratorioMapeo,
)
from oportunidades.services.dataset_export_service import exportar_dataset_productos_csv, exportar_lote_captura_csv
from oportunidades.services.importacion_service import procesar_importacion
from oportunidades.services.extractor_web_service import extraer_productos_preview
from oportunidades.services.laboratorio_mapeo_service import crear_sesion_laboratorio
from oportunidades.services.lotes_captura_service import (
    crear_lote_captura, finalizar_lote_captura, marcar_lote_descartado,
    marcar_lote_validado, registrar_detalle_lote,
)
from oportunidades.services.procesamiento_preview_service import procesar_resultado_preview


class Etapa318LotesCapturaTests(TestCase):
    def setUp(self):
        self.fuente = FuenteWeb.objects.create(
            nombre="Fuente lotes", url_base="https://lotes.example/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
        )
        self.categoria = CategoriaInteres.objects.create(nombre="Cocina lotes", palabra_clave="cocina lotes")
        self.canonico = ProductoCanonico.objects.create(nombre_normalizado="producto lote", categoria=self.categoria)

    def _lote(self):
        return crear_lote_captura("manual", fuente_web=self.fuente, nombre="Lote prueba")

    def _producto(self, lote=None):
        producto = ProductoFuente.objects.create(
            producto_canonico=self.canonico, fuente_web=self.fuente, lote_origen=lote,
            titulo_original="Producto lote", url_producto="https://lotes.example/producto",
            condicion=Producto.CONDICION_NUEVO,
        )
        precio = PrecioFuente.objects.create(
            producto_fuente=producto, lote_captura=lote, precio=Decimal("1000"),
            precio_lista=Decimal("1200"), precio_oportunidad=Decimal("1000"), origen_dato=PrecioFuente.ORIGEN_MANUAL,
        )
        return producto, precio

    def _extractor(self):
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente, semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO,
            permite_scraping=True, robots_txt_revisado=True, terminos_revisados=True,
        )
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente, nombre="Extractor lotes",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO, estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_revision_manual=False, respeta_politica_fuente=True,
        )
        ConfiguracionExtractorWeb.objects.create(
            conector=conector, url_inicio=self.fuente.url_base,
            pagina_prueba_url="https://lotes.example/cocina/", dominio_permitido="lotes.example",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_JSON_LD, habilitado=True, solo_preview=True,
        )
        return conector

    def test_crear_lote_captura(self):
        self.assertEqual(self._lote().fuente_web, self.fuente)

    def test_crear_detalle_lote_captura(self):
        lote = self._lote()
        self.assertEqual(registrar_detalle_lote(lote, "detectado").lote, lote)

    def test_crear_lote_captura_service(self):
        lote = crear_lote_captura("manual", fuente_web=self.fuente)
        self.assertIn("Fuente lotes", lote.nombre)

    def test_finalizar_lote_recalcula_contadores(self):
        lote = self._lote()
        producto, precio = self._producto(lote)
        registrar_detalle_lote(lote, "procesado", producto_fuente=producto, precio_fuente=precio)
        finalizar_lote_captura(lote)
        lote.refresh_from_db()
        self.assertEqual(lote.productos_procesados, 1)
        self.assertEqual(lote.precios_creados, 1)

    def test_marcar_lote_descartado(self):
        lote = marcar_lote_descartado(self._lote(), "mala calidad")
        self.assertTrue(lote.excluir_ml)
        self.assertFalse(lote.apto_dataset)

    def test_marcar_lote_validado(self):
        lote = marcar_lote_validado(self._lote())
        self.assertEqual(lote.estado, LoteCaptura.ESTADO_VALIDADO)

    def test_laboratorio_crea_lote_captura(self):
        sesion = crear_sesion_laboratorio({
            "ok": True, "url": "https://lotes.example/cocina/", "status_code": 200,
            "productos_detectados": [], "selectores_sugeridos": {}, "bloqueos_detectados": [],
        }, self.fuente)
        self.assertTrue(sesion.lotes_captura.exists())

    def test_resultado_laboratorio_vincula_lote(self):
        sesion = crear_sesion_laboratorio({
            "ok": True, "url": "https://lotes.example/cocina/", "status_code": 200,
            "productos_detectados": [{"titulo": "Uno", "precio_decimal": Decimal("10")}],
            "selectores_sugeridos": {}, "bloqueos_detectados": [],
        }, self.fuente)
        self.assertIsNotNone(sesion.resultados.first().lote_captura_id)

    @patch("oportunidades.services.extractor_web_service.hacer_request_extractor")
    def test_preview_extractor_crea_lote(self, request_mock):
        request_mock.return_value = {"ok": True, "text": '<script type="application/ld+json">{"@type":"Product","name":"Producto web","offers":{"price":"1000"}}</script>'}
        ejecucion = extraer_productos_preview(self._extractor())
        self.assertTrue(ejecucion.lotes_captura.exists())

    @patch("oportunidades.services.extractor_web_service.hacer_request_extractor")
    def test_resultado_extraccion_vincula_lote(self, request_mock):
        request_mock.return_value = {"ok": True, "text": '<script type="application/ld+json">{"@type":"Product","name":"Producto web","url":"https://lotes.example/web","offers":{"price":"1000"}}</script>'}
        ejecucion = extraer_productos_preview(self._extractor())
        self.assertIsNotNone(ejecucion.resultados_web.first().lote_captura_id)

    def test_procesar_preview_asigna_lote_a_producto_precio(self):
        conector = self._extractor()
        lote = crear_lote_captura("extractor_web", fuente_web=self.fuente, conector=conector, extractor=conector.configuracion_web)
        resultado = ResultadoExtraccionWeb.objects.create(
            ejecucion=conector.ejecuciones.create(), lote_captura=lote, titulo="Producto preview lote",
            precio_decimal=Decimal("900"), precio_oportunidad_decimal=Decimal("900"),
            url_producto="https://lotes.example/preview",
        )
        procesado = procesar_resultado_preview(resultado)
        self.assertEqual(procesado["producto_fuente"].lote_origen, lote)
        self.assertEqual(procesado["precio"].lote_captura, lote)

    def test_procesar_preview_crea_detalle_lote(self):
        conector = self._extractor()
        lote = crear_lote_captura("extractor_web", fuente_web=self.fuente, conector=conector, extractor=conector.configuracion_web)
        resultado = ResultadoExtraccionWeb.objects.create(
            ejecucion=conector.ejecuciones.create(), lote_captura=lote, titulo="Detalle preview lote",
            precio_decimal=Decimal("800"), precio_oportunidad_decimal=Decimal("800"),
            url_producto="https://lotes.example/detalle-preview",
        )
        procesar_resultado_preview(resultado)
        self.assertTrue(lote.detalles.filter(estado="procesado", resultado_extraccion=resultado).exists())

    def test_importacion_crea_lote_captura(self):
        archivo = SimpleUploadedFile("productos.csv", b"titulo,precio,url\nProducto CSV,1500,https://lotes.example/csv\n", content_type="text/csv")
        importacion = ImportacionProductos.objects.create(fuente_web=self.fuente, archivo=archivo, tipo_archivo="csv")
        procesar_importacion(importacion)
        self.assertTrue(importacion.lotes_captura.exists())
        self.assertTrue(importacion.lotes_captura.first().precios.exists())

    def test_export_dataset_incluye_lote(self):
        self._producto(self._lote())
        cabecera = exportar_dataset_productos_csv().getvalue().splitlines()[0]
        self.assertIn("lote_captura_id", cabecera)
        self.assertIn("lote_excluir_ml", cabecera)

    def test_export_dataset_excluye_lote_ml(self):
        lote = self._lote()
        lote.excluir_ml = True
        lote.save(update_fields=["excluir_ml"])
        self._producto(lote)
        self.assertEqual(len(list(csv.reader(exportar_dataset_productos_csv().getvalue().splitlines()))), 1)

    def test_export_lote_captura_csv(self):
        lote = self._lote()
        self._producto(lote)
        self.assertIn("Producto lote", exportar_lote_captura_csv(lote).getvalue())

    def test_lotes_captura_lista_carga(self):
        self._lote()
        self.assertEqual(Client(HTTP_HOST="localhost").get("/lotes-captura/").status_code, 200)

    def test_lote_captura_detalle_carga(self):
        lote = self._lote()
        response = Client(HTTP_HOST="localhost").get(f"/lotes-captura/{lote.id}/")
        self.assertEqual(response.status_code, 200)

    def test_lote_captura_accion_validar(self):
        lote = self._lote()
        response = Client(HTTP_HOST="localhost").post(f"/lotes-captura/{lote.id}/validar/")
        self.assertEqual(response.status_code, 302)

    def test_comandos_listar_y_recalcular(self):
        self._lote()
        salida = StringIO()
        call_command("listar_lotes_captura", stdout=salida)
        call_command("recalcular_lotes_captura", stdout=salida)
        self.assertIn("Lotes recalculados", salida.getvalue())

    def test_menu_contiene_lotes_captura(self):
        self.assertContains(Client(HTTP_HOST="localhost").get("/lotes-captura/"), "Lotes de captura")

    def test_manual_operativo_incluye_lotes_captura(self):
        manual = Path(__file__).resolve().parents[1] / "docs" / "manual_operativo_radar.md"
        contenido = manual.read_text(encoding="utf-8")
        self.assertIn("Lotes de captura y trazabilidad", contenido)
        self.assertIn("Flujo recomendado antes de cargar muchos datos", contenido)
