from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from oportunidades.models import CategoriaInteres, FuenteWeb, ItemRanking, LoteRanking, PrecioFuente, Producto, ProductoCanonico, ProductoFuente
from oportunidades.services.categorias_service import asegurar_categorias_supermercado
from oportunidades.services.normalizacion_supermercado_service import calcular_presentacion, calcular_promocion, convertir_a_base, es_oportunidad_bebida
from oportunidades.services.ranking_import_service import confirmar_importacion_ranking, limpiar_markdown, parsear_tabla_ranking, previsualizar_ranking


TABLA = """| Ranking | Producto | Categoria | Tienda donde aparece fuerte | Senal de venta | URL |
|---:|---|---|---|---|---|
| 1 | **Taladro atornillador percutor Lusqtoff 18V** | Herramientas electricas | Mercado Libre | Figura como 1 mas vendido. | [ver](https://www.mercadolibre.com.ar/mas-vendidos/MLA5228) |
| 2 | Set herramientas Black+Decker 125 piezas | Kit de herramientas | Mercado Libre | Aparece destacado. | https://listado.mercadolibre.com.ar/kit-herramientas |
"""


class RankingImportTests(TestCase):
    def setUp(self):
        asegurar_categorias_supermercado()
        self.fuente = FuenteWeb.objects.create(nombre="Mercado Libre", url_base="https://www.mercadolibre.com.ar/", tipo_fuente=FuenteWeb.TIPO_MARKETPLACE)
        self.categoria = CategoriaInteres.objects.get(slug="herramientas")
        self.canonico = ProductoCanonico.objects.create(nombre_normalizado="taladro atornillador percutor lusqtoff 18v", categoria=self.categoria)
        self.producto = ProductoFuente.objects.create(
            producto_canonico=self.canonico,
            fuente_web=self.fuente,
            titulo_original="Taladro atornillador percutor Lusqtoff 18V",
            url_producto="https://www.mercadolibre.com.ar/mas-vendidos/MLA5228",
            condicion=Producto.CONDICION_NUEVO,
        )

    def _datos_lote(self, preview, fecha=date(2026, 7, 18), estado=LoteRanking.ESTADO_BORRADOR):
        return {
            "nombre": "Herramientas con senales de alta venta",
            "tipo_ranking": LoteRanking.TIPO_ALTA_VENTA,
            "alcance": "herramientas",
            "categoria_id": self.categoria.id,
            "fecha_referencia": fecha,
            "origen": "Radar ChatGPT - carga manual",
            "metodologia": "Tabla pegada",
            "estado": estado,
            "hash_importacion": preview["hash"],
        }

    def test_importacion_markdown(self):
        rows, errores = parsear_tabla_ranking(TABLA, "markdown")
        self.assertEqual(len(rows), 2)
        self.assertFalse(errores)

    def test_importacion_csv(self):
        csv = "Ranking,Producto,Categoria,Tienda,Senal,URL\n1,Coca 2.25 x6,Gaseosas,Mayorista,Alta rotacion,https://example.com\n"
        rows, errores = parsear_tabla_ranking(csv, "csv")
        self.assertEqual(rows[0]["producto"], "Coca 2.25 x6")
        self.assertFalse(errores)

    def test_limpia_negritas_markdown(self):
        self.assertEqual(limpiar_markdown("**Producto**"), "Producto")

    def test_interpreta_enlaces_markdown(self):
        preview = previsualizar_ranking(TABLA, date(2026, 7, 18), alcance="herramientas")
        self.assertEqual(preview["filas"][0]["url"], "https://www.mercadolibre.com.ar/mas-vendidos/MLA5228")

    def test_validacion_columnas(self):
        _, errores = parsear_tabla_ranking("| Producto |\n|---|\n| Demo |", "markdown")
        self.assertTrue(any("posicion" in error for error in errores))

    def test_detecta_filas_invalidas(self):
        preview = previsualizar_ranking("| Ranking | Producto | Categoria | Tienda | Senal | URL |\n|---|---|---|---|---|---|\n| 1 | | Cat | T | S | https://e.com |")
        self.assertFalse(preview["filas"][0]["valida"])

    def test_previene_lotes_duplicados(self):
        preview = previsualizar_ranking(TABLA, date(2026, 7, 18), alcance="herramientas")
        confirmar_importacion_ranking(self._datos_lote(preview), preview["filas"], TABLA)
        with self.assertRaises(ValueError):
            confirmar_importacion_ranking(self._datos_lote(preview), preview["filas"], TABLA)

    def test_relaciona_producto_existente(self):
        preview = previsualizar_ranking(TABLA, date(2026, 7, 18), alcance="herramientas")
        self.assertEqual(preview["filas"][0]["producto_fuente_id"], self.producto.id)

    def test_item_sin_producto_relacionado(self):
        preview = previsualizar_ranking(TABLA.replace("Set herramientas", "Producto inexistente raro"), date(2026, 7, 18), alcance="herramientas")
        self.assertIsNone(preview["filas"][1]["producto_fuente_id"])

    def test_comparacion_entre_dos_lotes(self):
        preview = previsualizar_ranking(TABLA, date(2026, 7, 17), alcance="herramientas")
        confirmar_importacion_ranking(self._datos_lote(preview, date(2026, 7, 17), LoteRanking.ESTADO_PUBLICADO), preview["filas"], TABLA)
        tabla2 = TABLA.replace("| 1 | **Taladro", "| 2 | **Taladro").replace("| 2 | Set herramientas", "| 1 | Set herramientas")
        preview2 = previsualizar_ranking(tabla2, date(2026, 7, 18), alcance="herramientas")
        lote2 = confirmar_importacion_ranking(self._datos_lote(preview2, date(2026, 7, 18), LoteRanking.ESTADO_PUBLICADO), preview2["filas"], tabla2)
        item = lote2.items.get(nombre_original__icontains="Taladro")
        self.assertEqual(item.posicion_anterior, 1)
        self.assertEqual(item.tendencia, ItemRanking.TENDENCIA_BAJO)

    def test_tendencias_nuevo_subio_bajo_se_mantuvo(self):
        tabla1 = TABLA + "| 3 | Producto estable | Herramientas | Mercado Libre | Ranking | https://e.com/3 |\n"
        preview1 = previsualizar_ranking(tabla1, date(2026, 7, 17), alcance="herramientas")
        confirmar_importacion_ranking(self._datos_lote(preview1, date(2026, 7, 17), LoteRanking.ESTADO_PUBLICADO), preview1["filas"], tabla1)
        tabla2 = """| Ranking | Producto | Categoria | Tienda | Senal | URL |
|---|---|---|---|---|---|
| 1 | Set herramientas Black+Decker 125 piezas | Herramientas | Mercado Libre | Ranking | https://listado.mercadolibre.com.ar/kit-herramientas |
| 2 | Taladro atornillador percutor Lusqtoff 18V | Herramientas | Mercado Libre | Ranking | https://www.mercadolibre.com.ar/mas-vendidos/MLA5228 |
| 3 | Producto estable | Herramientas | Mercado Libre | Ranking | https://e.com/3 |
| 4 | Producto nuevo | Herramientas | Mercado Libre | Ranking | https://e.com/4 |
"""
        preview2 = previsualizar_ranking(tabla2, date(2026, 7, 18), alcance="herramientas")
        lote2 = confirmar_importacion_ranking(self._datos_lote(preview2, date(2026, 7, 18), LoteRanking.ESTADO_PUBLICADO), preview2["filas"], tabla2)
        tendencias = {i.nombre_original: i.tendencia for i in lote2.items.all()}
        self.assertIn(ItemRanking.TENDENCIA_SUBIO, tendencias.values())
        self.assertIn(ItemRanking.TENDENCIA_BAJO, tendencias.values())
        self.assertIn(ItemRanking.TENDENCIA_MANTUVO, tendencias.values())
        self.assertIn(ItemRanking.TENDENCIA_NUEVO, tendencias.values())

    def test_permisos_importador_requiere_staff(self):
        response = self.client.post(reverse("oportunidades:ranking_importar"), {})
        self.assertEqual(response.status_code, 403)

    def test_filtros_rankings(self):
        preview = previsualizar_ranking(TABLA, date(2026, 7, 18), alcance="herramientas")
        confirmar_importacion_ranking(self._datos_lote(preview, estado=LoteRanking.ESTADO_PUBLICADO), preview["filas"], TABLA)
        response = self.client.get(reverse("oportunidades:api_rankings_actual"), {"tipo": LoteRanking.TIPO_ALTA_VENTA, "alcance": "herramientas"})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)

    def test_render_pantalla_publica(self):
        response = self.client.get(reverse("oportunidades:rankings_lista"))
        self.assertEqual(response.status_code, 200)

    def test_enlace_producto_existente_en_ranking(self):
        preview = previsualizar_ranking(TABLA, date(2026, 7, 18), alcance="herramientas")
        lote = confirmar_importacion_ranking(self._datos_lote(preview), preview["filas"], TABLA)
        self.assertEqual(lote.items.first().producto_fuente_id, self.producto.id)

    def test_importador_form_preview(self):
        user = get_user_model().objects.create_user("admin", password="x", is_staff=True)
        self.client.force_login(user)
        response = self.client.post(
            reverse("oportunidades:ranking_importar"),
            {
                "accion": "preview",
                "nombre": "Herramientas con senales de alta venta",
                "tipo_ranking": LoteRanking.TIPO_ALTA_VENTA,
                "alcance": "herramientas",
                "categoria": self.categoria.id,
                "fecha_referencia": "2026-07-18",
                "origen": "Radar ChatGPT - carga manual",
                "formato": "markdown",
                "estado": LoteRanking.ESTADO_BORRADOR,
                "texto": TABLA,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Filas detectadas")


class NormalizacionSupermercadoTests(TestCase):
    def test_calculo_por_litro_individual(self):
        r = calcular_presentacion(contenido_neto_por_unidad=Decimal("2.25"), unidad_medida_original="litro", precio_final_total=Decimal("2500"))
        self.assertEqual(r["precio_por_litro"], Decimal("1111.11"))

    def test_calculo_pack_por_litro_y_unidad(self):
        r = calcular_presentacion(tipo_presentacion="pack", unidades_por_presentacion=6, contenido_neto_por_unidad=Decimal("2.25"), unidad_medida_original="litro", precio_final_total=Decimal("12000"))
        self.assertEqual(r["contenido_total"], Decimal("13.500"))
        self.assertEqual(r["precio_por_litro"], Decimal("888.89"))
        self.assertEqual(r["precio_por_unidad"], Decimal("2000.00"))

    def test_calculo_fardo(self):
        r = calcular_presentacion(tipo_presentacion="fardo", unidades_por_presentacion=12, contenido_neto_por_unidad=Decimal("1.5"), unidad_medida_original="litro", precio_final_total=Decimal("15000"))
        self.assertEqual(r["contenido_total"], Decimal("18.000"))
        self.assertEqual(r["precio_por_litro"], Decimal("833.33"))
        self.assertEqual(r["precio_por_unidad"], Decimal("1250.00"))

    def test_conversion_ml_litro(self):
        self.assertEqual(convertir_a_base(1500, "ml"), (Decimal("1.500"), "litro"))

    def test_conversion_g_kg(self):
        self.assertEqual(convertir_a_base(500, "g"), (Decimal("0.500"), "kg"))

    def test_promocion_2x1(self):
        r = calcular_promocion("2x1", precio_unitario=1000)
        self.assertEqual(r["cantidad_total_recibida"], Decimal("2.00"))
        self.assertEqual(r["precio_total_efectivo"], Decimal("1000.00"))

    def test_promocion_3x2(self):
        r = calcular_promocion("3x2", precio_unitario=1000)
        self.assertEqual(r["cantidad_total_recibida"], Decimal("3.00"))
        self.assertEqual(r["precio_total_efectivo"], Decimal("2000.00"))

    def test_segunda_unidad_descuento(self):
        r = calcular_promocion("segunda_descuento", precio_unitario=1000, descuento_segunda=50)
        self.assertEqual(r["precio_total_efectivo"], Decimal("1500.00"))

    def test_umbral_exacto_20_por_ciento(self):
        r = es_oportunidad_bebida(80, 100)
        self.assertTrue(r["es_oportunidad"])
        self.assertEqual(r["descuento"], Decimal("20.00"))

    def test_conservacion_multiprecio_con_modelo_precio_existente(self):
        campos = {field.name for field in PrecioFuente._meta.fields}
        self.assertIn("precio_lista", campos)
        self.assertIn("precio_transferencia", campos)
        self.assertIn("precio_tarjeta", campos)
