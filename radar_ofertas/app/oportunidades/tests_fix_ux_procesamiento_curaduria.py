from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import Client, TestCase

from oportunidades.models import (
    CategoriaFuente,
    CategoriaInteres,
    ConfiguracionExtractorWeb,
    ConectorFuente,
    EjecucionConector,
    FuenteWeb,
    LoteCaptura,
    PoliticaExtraccionFuente,
    PrecioFuente,
    ProductoCanonico,
    ProductoFuente,
    ResultadoExtraccionWeb,
)
from oportunidades.services.procesamiento_preview_service import procesar_resultados_seleccionados


class FixUxProcesamientoCuraduriaTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")
        self.fuente = FuenteWeb.objects.create(
            nombre="Ganga Home",
            url_base="https://www.gangahome.com.ar/",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            rubro_principal="hogar",
            activa=True,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            permite_scraping=True,
            robots_txt_revisado=True,
            terminos_revisados=True,
        )
        self.conector = ConectorFuente.objects.create(
            fuente_web=self.fuente,
            nombre="Ganga Home - Extractor",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_revision_manual=False,
            respeta_politica_fuente=True,
        )
        self.extractor = ConfiguracionExtractorWeb.objects.create(
            conector=self.conector,
            url_inicio="https://www.gangahome.com.ar/",
            url_categoria="https://www.gangahome.com.ar/cocina/",
            pagina_prueba_url="https://www.gangahome.com.ar/cocina/",
            dominio_permitido="gangahome.com.ar",
            modo_extraccion=ConfiguracionExtractorWeb.MODO_MIXTO,
            max_paginas=1,
            max_productos=10,
            delay_segundos=Decimal("2.00"),
            habilitado=True,
            solo_preview=True,
        )
        self.ejecucion = EjecucionConector.objects.create(conector=self.conector, estado=EjecucionConector.ESTADO_FINALIZADA)
        self.lote = LoteCaptura.objects.create(
            nombre="Ganga Home - cocina",
            origen=LoteCaptura.ORIGEN_EXTRACTOR_WEB,
            fuente_web=self.fuente,
            conector=self.conector,
            extractor=self.extractor,
            ejecucion_conector=self.ejecucion,
            url_origen="https://www.gangahome.com.ar/cocina/",
        )
        self.categoria_interes = CategoriaInteres.objects.create(nombre="Hogar", palabra_clave="hogar")
        self.categoria_fuente = CategoriaFuente.objects.create(fuente=self.fuente, nombre="Cocina", categoria_normalizada=self.categoria_interes)
        self.canonico = ProductoCanonico.objects.create(nombre_normalizado="producto prueba", categoria=self.categoria_interes)

    def crear_resultado(self, **kwargs):
        datos = {
            "ejecucion": self.ejecucion,
            "lote_captura": self.lote,
            "titulo": "Producto prueba",
            "precio_decimal": Decimal("1000.00"),
            "precio_lista_decimal": Decimal("1200.00"),
            "precio_transferencia_decimal": Decimal("900.00"),
            "precio_tarjeta_decimal": Decimal("1100.00"),
            "precio_oportunidad_decimal": Decimal("900.00"),
            "tipo_precio_oportunidad": PrecioFuente.TIPO_PRECIO_TRANSFERENCIA,
            "url_producto": "https://www.gangahome.com.ar/productos/producto-prueba/",
            "imagen_url": "https://www.gangahome.com.ar/producto.jpg",
            "procesable": True,
            "seleccionado": True,
        }
        datos.update(kwargs)
        return ResultadoExtraccionWeb.objects.create(**datos)

    def crear_producto(self, **kwargs):
        datos = {
            "lote_origen": self.lote,
            "producto_canonico": self.canonico,
            "fuente_web": self.fuente,
            "categoria_fuente": self.categoria_fuente,
            "titulo_original": "Producto prueba",
            "url_producto": "https://www.gangahome.com.ar/radar-preview/producto-prueba",
            "url_tecnica_generada": True,
            "condicion": "desconocido",
            "requiere_revision": True,
        }
        datos.update(kwargs)
        return ProductoFuente.objects.create(**datos)

    def test_resultados_preview_tiene_accion_seleccionar_todos_visibles(self):
        self.crear_resultado()
        response = self.client.get(f"/extractores/{self.extractor.pk}/resultados/")
        self.assertContains(response, "Seleccionar todos los visibles")

    def test_resultados_preview_tiene_accion_procesar_todos_procesables(self):
        self.crear_resultado()
        response = self.client.get(f"/extractores/{self.extractor.pk}/resultados/")
        self.assertContains(response, "Procesar todos los procesables del lote")

    def test_procesar_todos_procesables_no_procesa_sin_precio(self):
        self.crear_resultado(precio_oportunidad_decimal=Decimal("0.00"), precio_decimal=Decimal("0.00"))
        resumen = procesar_resultados_seleccionados(self.ejecucion, limite=20)
        self.assertEqual(resumen["procesados"], 0)
        self.assertEqual(ProductoFuente.objects.count(), 0)

    def test_procesar_todos_procesables_mantiene_lote(self):
        self.crear_resultado()
        procesar_resultados_seleccionados(self.ejecucion, limite=20)
        producto = ProductoFuente.objects.get()
        precio = PrecioFuente.objects.get()
        self.assertEqual(producto.lote_origen, self.lote)
        self.assertEqual(precio.lote_captura, self.lote)

    def test_curaduria_muestra_subtitulo_revision_calidad(self):
        self.crear_producto()
        response = self.client.get("/curaduria/productos/")
        self.assertContains(response, "Revision de calidad de productos ya procesados")

    def test_curaduria_tiene_acciones_masivas(self):
        self.crear_producto()
        response = self.client.get("/curaduria/productos/")
        self.assertContains(response, "Marcar seleccionados como revisados")
        self.assertContains(response, "Recalcular calidad seleccionados")

    def test_curaduria_filtra_url_tecnica(self):
        tecnico = self.crear_producto(titulo_original="Tecnico")
        self.crear_producto(titulo_original="Real", url_producto="https://www.gangahome.com.ar/productos/real/", url_tecnica_generada=False)
        response = self.client.get("/curaduria/productos/?url=tecnica")
        self.assertContains(response, tecnico.titulo_original)
        self.assertNotContains(response, "Real")

    def test_curaduria_filtra_sin_lote(self):
        self.crear_producto(titulo_original="Con lote")
        sin_lote = self.crear_producto(titulo_original="Sin lote", lote_origen=None)
        response = self.client.get("/curaduria/productos/?lote=sin")
        self.assertContains(response, sin_lote.titulo_original)
        self.assertNotContains(response, "Con lote")

    def test_curaduria_muestra_lote_origen(self):
        self.crear_producto()
        response = self.client.get("/curaduria/productos/")
        self.assertContains(response, self.lote.nombre)

    def test_curaduria_muestra_no_detectado_en_transferencia_si_cero(self):
        producto = self.crear_producto(url_producto="https://www.gangahome.com.ar/productos/producto-prueba/", url_tecnica_generada=False)
        PrecioFuente.objects.create(producto_fuente=producto, lote_captura=self.lote, precio=Decimal("1000.00"), precio_oportunidad=Decimal("1000.00"), origen_dato=PrecioFuente.ORIGEN_SCRAPING)
        response = self.client.get("/curaduria/productos/")
        self.assertContains(response, "No detectado")

    def test_lote_no_valida_sin_advertencia_si_hay_url_tecnica(self):
        self.crear_producto()
        response = self.client.post(f"/lotes-captura/{self.lote.pk}/validar/", follow=True)
        self.lote.refresh_from_db()
        self.assertNotEqual(self.lote.estado, LoteCaptura.ESTADO_VALIDADO)
        self.assertContains(response, "Antes de validar")

    def test_reparar_urls_productos_desde_preview_command(self):
        producto = self.crear_producto()
        self.crear_resultado(titulo=producto.titulo_original, url_producto="https://www.gangahome.com.ar/productos/url-real/")
        salida = StringIO()
        call_command("reparar_urls_productos_desde_preview", "--limite", "50", stdout=salida)
        producto.refresh_from_db()
        self.assertEqual(producto.url_producto, "https://www.gangahome.com.ar/productos/url-real/")
        self.assertFalse(producto.url_tecnica_generada)
        self.assertIn("corregidos=1", salida.getvalue())

    def test_producto_con_url_real_muestra_abrir(self):
        self.crear_producto(url_producto="https://www.gangahome.com.ar/productos/real/", url_tecnica_generada=False)
        response = self.client.get("/curaduria/productos/")
        self.assertContains(response, "Abrir")

    def test_producto_con_url_tecnica_muestra_badge(self):
        self.crear_producto()
        response = self.client.get("/curaduria/productos/")
        self.assertContains(response, "URL tecnica")

    def test_manual_operativo_explica_preview_procesamiento_curaduria(self):
        manual = Path(__file__).resolve().parents[1] / "docs" / "manual_operativo_radar.md"
        contenido = manual.read_text(encoding="utf-8")
        self.assertIn("Diferencia entre Preview, Procesamiento y Curaduria", contenido)
        self.assertIn("Curaduria revisa calidad de productos ya procesados", contenido)

    def test_manual_operativo_explica_procesamiento_masivo(self):
        manual = Path(__file__).resolve().parents[1] / "docs" / "manual_operativo_radar.md"
        contenido = manual.read_text(encoding="utf-8")
        self.assertIn("Procesamiento masivo seguro", contenido)
        self.assertIn("Procesar todos los procesables del lote", contenido)
