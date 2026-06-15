import csv
from decimal import Decimal

from django.test import Client, TestCase

from oportunidades.models import (
    CategoriaInteres,
    ComparacionPrecio,
    FuenteWeb,
    PrecioFuente,
    ProductoCanonico,
    ProductoFuente,
    SugerenciaMatchingProducto,
)
from oportunidades.services.comparacion_service import calcular_comparacion_producto_canonico
from oportunidades.services.dataset_export_service import exportar_dataset_productos_csv
from oportunidades.services.matching_productos_service import (
    aceptar_sugerencia_matching,
    calcular_score_similitud_producto,
    extraer_atributos_basicos,
    extraer_tokens_producto,
    generar_sugerencias_matching,
    normalizar_texto_matching,
    revisar_sugerencia_matching,
)


class Etapa316MatchingTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(nombre="Cocina", palabra_clave="cocina")
        self.fuente_a = FuenteWeb.objects.create(nombre="Ganga Home", url_base="https://gangahome.com.ar", tipo_fuente="tienda_online")
        self.fuente_b = FuenteWeb.objects.create(nombre="Otra Tienda", url_base="https://otra.example", tipo_fuente="tienda_online")

    def producto(self, fuente, titulo, canonico=None, precio=Decimal("10000")):
        producto = ProductoFuente.objects.create(
            producto_canonico=canonico,
            fuente_web=fuente,
            titulo_original=titulo,
            url_producto=f"https://{fuente.pk}.example/producto/{ProductoFuente.objects.count() + 1}",
            imagen_url="https://img.example/producto.jpg",
            condicion="nuevo",
        )
        PrecioFuente.objects.create(
            producto_fuente=producto,
            precio=precio,
            precio_lista=precio + Decimal("2000"),
            precio_transferencia=precio,
            precio_oportunidad=precio,
            tipo_precio_oportunidad=PrecioFuente.TIPO_PRECIO_TRANSFERENCIA,
            origen_dato=PrecioFuente.ORIGEN_MANUAL,
        )
        return producto

    def par_similar(self):
        return (
            self.producto(self.fuente_a, "Set x5 Frascos de Vidrio GH-2490"),
            self.producto(self.fuente_b, "Set de 5 frascos vidrio GH2490 cocina con tapa", precio=Decimal("8000")),
        )

    def test_normalizar_texto_matching(self):
        self.assertEqual(normalizar_texto_matching("OFERTA: Frascos de Vidrio GH-2490"), "frascos de vidrio gh2490")

    def test_extraer_tokens_producto(self):
        self.assertEqual(extraer_tokens_producto("Set x5 Frascos de Vidrio GH-2490"), ["set", "x5", "frascos", "vidrio", "gh2490"])

    def test_extraer_atributos_cantidad(self):
        self.assertEqual(extraer_atributos_basicos("Pack 5 frascos")["cantidad"], "5")

    def test_extraer_atributos_material(self):
        self.assertEqual(extraer_atributos_basicos("Frasco de vidrio")["material"], "vidrio")

    def test_extraer_atributos_medidas(self):
        self.assertEqual(extraer_atributos_basicos("Organizador 30 x 40 cm")["medidas"], "30x40cm")

    def test_extraer_codigo_modelo(self):
        self.assertEqual(extraer_atributos_basicos("Frasco GH-2490")["codigo_modelo"], "gh2490")

    def test_score_similitud_alto_mismo_producto_nombre_distinto(self):
        producto_a, producto_b = self.par_similar()
        self.assertGreaterEqual(calcular_score_similitud_producto(producto_a, producto_b)["score"], 80)

    def test_score_similitud_bajo_productos_distintos(self):
        producto_a = self.producto(self.fuente_a, "Frasco vidrio 500ml")
        producto_b = self.producto(self.fuente_b, "Sillon madera beige 2 cuerpos")
        self.assertLess(calcular_score_similitud_producto(producto_a, producto_b)["score"], 40)

    def test_score_similitud_modelo_igual_suma_mucho(self):
        producto_a = self.producto(self.fuente_a, "Frascos GH-2490")
        producto_b = self.producto(self.fuente_b, "Organizador modelo GH2490")
        self.assertGreaterEqual(calcular_score_similitud_producto(producto_a, producto_b)["score"], 40)

    def test_score_similitud_material_cantidad_suman(self):
        producto_a = self.producto(self.fuente_a, "Pack 5 frascos vidrio")
        producto_b = self.producto(self.fuente_b, "Set x5 contenedores vidrio")
        resultado = calcular_score_similitud_producto(producto_a, producto_b)
        self.assertTrue(any("cantidad" in motivo for motivo in resultado["motivos"]))
        self.assertTrue(any("material" in motivo for motivo in resultado["motivos"]))

    def test_generar_sugerencia_matching_no_duplica(self):
        self.par_similar()
        generar_sugerencias_matching(limite=50)
        generar_sugerencias_matching(limite=50)
        self.assertEqual(SugerenciaMatchingProducto.objects.count(), 1)

    def test_generar_sugerencia_matching_distintas_fuentes(self):
        self.par_similar()
        resumen = generar_sugerencias_matching(limite=50)
        self.assertEqual(resumen["creadas"], 1)

    def test_no_sugerir_producto_consigomismo(self):
        producto, _ = self.par_similar()
        with self.assertRaises(ValueError):
            SugerenciaMatchingProducto.objects.create(producto_a=producto, producto_b=producto)

    def test_rechazada_no_se_recrea(self):
        producto_a, producto_b = self.par_similar()
        sugerencia = SugerenciaMatchingProducto.objects.create(producto_a=producto_a, producto_b=producto_b, score=90, nivel="alto", estado="rechazada")
        generar_sugerencias_matching(limite=50)
        self.assertEqual(SugerenciaMatchingProducto.objects.get().pk, sugerencia.pk)

    def test_aceptar_matching_vincula_mismo_producto_canonico(self):
        producto_a, producto_b = self.par_similar()
        sugerencia = SugerenciaMatchingProducto.objects.create(producto_a=producto_a, producto_b=producto_b, score=90, nivel="alto")
        aceptar_sugerencia_matching(sugerencia)
        producto_a.refresh_from_db(); producto_b.refresh_from_db()
        self.assertEqual(producto_a.producto_canonico_id, producto_b.producto_canonico_id)

    def test_aceptar_matching_recalcula_comparacion(self):
        producto_a, producto_b = self.par_similar()
        sugerencia = SugerenciaMatchingProducto.objects.create(producto_a=producto_a, producto_b=producto_b, score=90, nivel="alto")
        canonico = aceptar_sugerencia_matching(sugerencia)
        self.assertTrue(ComparacionPrecio.objects.filter(producto_canonico=canonico, cantidad_fuentes=2).exists())

    def test_aceptar_matching_no_borra_historial(self):
        producto_a, producto_b = self.par_similar()
        total = PrecioFuente.objects.count()
        sugerencia = SugerenciaMatchingProducto.objects.create(producto_a=producto_a, producto_b=producto_b, score=90, nivel="alto")
        aceptar_sugerencia_matching(sugerencia)
        self.assertEqual(PrecioFuente.objects.count(), total)

    def test_rechazar_matching(self):
        producto_a, producto_b = self.par_similar()
        sugerencia = SugerenciaMatchingProducto.objects.create(producto_a=producto_a, producto_b=producto_b, score=90, nivel="alto")
        revisar_sugerencia_matching(sugerencia, "rechazada", "No coincide")
        sugerencia.refresh_from_db()
        self.assertEqual(sugerencia.estado, "rechazada")
        self.assertIsNotNone(sugerencia.fecha_revision)

    def test_matching_productos_view_carga(self):
        response = Client(HTTP_HOST="localhost").get("/matching/productos/")
        self.assertEqual(response.status_code, 200)

    def test_matching_detalle_view_carga(self):
        producto_a, producto_b = self.par_similar()
        sugerencia = SugerenciaMatchingProducto.objects.create(producto_a=producto_a, producto_b=producto_b, score=90, nivel="alto")
        response = Client(HTTP_HOST="localhost").get(f"/matching/productos/{sugerencia.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_productos_multifuente_muestra_varias_fuentes(self):
        canonico = ProductoCanonico.objects.create(nombre_normalizado="frascos vidrio", categoria=self.categoria)
        self.producto(self.fuente_a, "Frascos vidrio", canonico)
        self.producto(self.fuente_b, "Set frascos vidrio", canonico)
        calcular_comparacion_producto_canonico(canonico)
        response = Client(HTTP_HOST="localhost").get("/productos-multifuente/?multiples=1")
        self.assertContains(response, "Ganga Home")
        self.assertContains(response, "Otra Tienda")

    def test_comparacion_producto_canonico_fuente_mas_barata(self):
        canonico = ProductoCanonico.objects.create(nombre_normalizado="frascos vidrio", categoria=self.categoria)
        self.producto(self.fuente_a, "Frascos", canonico, Decimal("10000"))
        barato = self.producto(self.fuente_b, "Frascos", canonico, Decimal("7000"))
        comparacion = calcular_comparacion_producto_canonico(canonico)
        self.assertEqual(comparacion.producto_fuente_mas_barato, barato)

    def test_comparacion_diferencia_pct(self):
        canonico = ProductoCanonico.objects.create(nombre_normalizado="frascos vidrio", categoria=self.categoria)
        self.producto(self.fuente_a, "Frascos", canonico, Decimal("100"))
        self.producto(self.fuente_b, "Frascos", canonico, Decimal("50"))
        comparacion = calcular_comparacion_producto_canonico(canonico)
        self.assertEqual(comparacion.diferencia_pct_min_max, Decimal("50.00"))

    def test_export_dataset_incluye_campos_matching(self):
        filas = list(csv.reader(exportar_dataset_productos_csv().getvalue().splitlines()))
        self.assertIn("score_matching", filas[0])
        self.assertIn("cantidad_fuentes_canonico", filas[0])
        self.assertIn("requiere_revision_matching", filas[0])
