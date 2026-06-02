from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from oportunidades.models import (
    CategoriaInteres,
    ConectorFuente,
    EjecucionConector,
    FuenteWeb,
    PoliticaExtraccionFuente,
    PrecioFuente,
    ProductoCanonico,
    ProductoFuente,
    ResultadoExtraccionWeb,
)
from oportunidades.services.backup_service import exportar_snapshot_json, importar_snapshot_json
from oportunidades.services.curaduria_service import (
    detectar_producto_fuente_duplicados,
    marcar_requiere_revision,
    reasignar_producto_canonico,
)
from oportunidades.services.dataset_export_service import exportar_dataset_productos_csv, exportar_historial_precios_csv
from oportunidades.services.entorno_service import entorno_no_persistente, obtener_advertencia_persistencia
from oportunidades.services.procesamiento_preview_service import procesar_resultado_preview
from oportunidades.services.ranking_comercial_service import calcular_score_comercial_producto_fuente


class Etapa312Tests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(nombre="Hogar", palabra_clave="hogar")
        self.fuente = FuenteWeb.objects.create(nombre="Ganga Home", url_base="https://gangahome.example/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE)
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO,
            permite_scraping=True,
            robots_txt_revisado=True,
            terminos_revisados=True,
        )
        self.canonico = ProductoCanonico.objects.create(nombre_normalizado="rallador bambu", categoria=self.categoria)
        self.producto = ProductoFuente.objects.create(
            producto_canonico=self.canonico,
            fuente_web=self.fuente,
            titulo_original="Rallador Bambu C/Mango",
            url_producto="https://gangahome.example/producto/rallador",
            imagen_url="https://gangahome.example/rallador.jpg",
            condicion="nuevo",
        )
        PrecioFuente.objects.create(
            producto_fuente=self.producto,
            precio=Decimal("21144.00"),
            precio_lista=Decimal("29986.00"),
            precio_transferencia=Decimal("21144.00"),
            precio_oportunidad=Decimal("21144.00"),
            tipo_precio_oportunidad=PrecioFuente.TIPO_PRECIO_TRANSFERENCIA,
            origen_dato=PrecioFuente.ORIGEN_SCRAPING,
        )

    @patch("oportunidades.services.entorno_service.es_render", return_value=True)
    @patch("oportunidades.services.entorno_service.usa_sqlite", return_value=True)
    def test_entorno_render_sqlite_advierte_no_persistente(self, *_):
        self.assertTrue(entorno_no_persistente())
        self.assertIn("SQLite en Render", obtener_advertencia_persistencia())

    @patch("oportunidades.services.entorno_service.es_render", return_value=False)
    def test_entorno_local_no_advierte(self, *_):
        self.assertEqual(obtener_advertencia_persistencia(), "")

    def test_marcar_producto_requiere_revision(self):
        marcar_requiere_revision(self.producto, "Revisar dato de prueba.")

        self.producto.refresh_from_db()
        self.assertTrue(self.producto.requiere_revision)
        self.assertIn("Revisar dato", self.producto.motivo_revision)

    def test_producto_sin_url_real_requiere_revision(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente,
            nombre="Extractor",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_revision_manual=False,
            respeta_politica_fuente=True,
        )
        from oportunidades.models import ConfiguracionExtractorWeb

        ConfiguracionExtractorWeb.objects.create(
            conector=conector,
            url_inicio="https://gangahome.example/",
            dominio_permitido="gangahome.example",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_JSON_LD,
            habilitado=True,
        )
        ejecucion = EjecucionConector.objects.create(conector=conector)
        resultado = ResultadoExtraccionWeb.objects.create(
            ejecucion=ejecucion,
            titulo="Set Salero",
            precio_decimal=Decimal("1000.00"),
            precio_oportunidad_decimal=Decimal("1000.00"),
            fuente_url="https://gangahome.example/cocina/",
        )

        procesado = procesar_resultado_preview(resultado)

        self.assertTrue(procesado["ok"])
        producto = procesado["producto_fuente"]
        self.assertTrue(producto.url_tecnica_generada)
        self.assertTrue(producto.requiere_revision)

    def test_detectar_duplicado_por_url(self):
        ProductoFuente.objects.create(
            producto_canonico=self.canonico,
            fuente_web=self.fuente,
            titulo_original="Rallador Bambu Mango",
            url_producto=self.producto.url_producto,
            condicion="nuevo",
        )

        duplicados = detectar_producto_fuente_duplicados(self.producto)

        self.assertTrue(duplicados)

    def test_reasignar_producto_canonico_recalcula(self):
        nuevo = ProductoCanonico.objects.create(nombre_normalizado="nuevo canonico", categoria=self.categoria)

        reasignar_producto_canonico(self.producto, nuevo)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.producto_canonico, nuevo)

    def test_exportar_dataset_productos_csv(self):
        contenido = exportar_dataset_productos_csv().getvalue()

        self.assertIn("producto_canonico_id", contenido)
        self.assertIn("Rallador Bambu", contenido)

    def test_exportar_historial_precios_csv(self):
        contenido = exportar_historial_precios_csv().getvalue()

        self.assertIn("precio_transferencia", contenido)
        self.assertIn("21144.00", contenido)

    def test_exportar_snapshot_json(self):
        contenido = exportar_snapshot_json()

        self.assertIn("oportunidades.fuenteweb", contenido)

    def test_importar_snapshot_dry_run_no_modifica(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".json", delete=False) as archivo:
            archivo.write(exportar_snapshot_json())
            archivo.flush()
            resumen = importar_snapshot_json(archivo.name, dry_run=True)

        self.assertTrue(resumen["dry_run"])
        self.assertGreater(resumen["objetos"], 0)

    def test_score_comercial_alto_con_transferencia_descuento_url_imagen(self):
        resultado = calcular_score_comercial_producto_fuente(self.producto)

        self.assertGreaterEqual(resultado["score"], 60)

    def test_score_comercial_bajo_sin_url_sin_imagen(self):
        self.producto.imagen_url = None
        self.producto.url_tecnica_generada = True
        self.producto.requiere_revision = True
        self.producto.save()

        resultado = calcular_score_comercial_producto_fuente(self.producto)

        self.assertLess(resultado["score"], 60)
