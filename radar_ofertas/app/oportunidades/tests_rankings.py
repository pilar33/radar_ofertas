from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from oportunidades.models import CategoriaInteres, FuenteWeb, ItemRanking, LoteRanking, PrecioFuente, Producto, ProductoCanonico, ProductoFuente
from oportunidades.services.categorias_service import asegurar_categorias_supermercado
from oportunidades.services.normalizacion_supermercado_service import calcular_presentacion, calcular_promocion, convertir_a_base, es_oportunidad_bebida
from oportunidades.services.ranking_import_service import confirmar_importacion_ranking, limpiar_markdown, parsear_tabla_ranking, previsualizar_ranking
from oportunidades.services.ranking_import_service import reparar_precios_normalizados_lote


TABLA = """| Ranking | Producto | Categoria | Tienda donde aparece fuerte | Senal de venta | URL |
|---:|---|---|---|---|---|
| 1 | **Taladro atornillador percutor Lusqtoff 18V** | Herramientas electricas | Mercado Libre | Figura como 1 mas vendido. | [ver](https://www.mercadolibre.com.ar/mas-vendidos/MLA5228) |
| 2 | Set herramientas Black+Decker 125 piezas | Kit de herramientas | Mercado Libre | Aparece destacado. | https://listado.mercadolibre.com.ar/kit-herramientas |
"""

TABLA_BEBIDAS_PRECIO_NORMALIZADO = """| Ranking | Producto                         | Tienda                 | Precio normalizado | Estado                   |
| ------: | -------------------------------- | ---------------------- | -----------------: | ------------------------ |
|       1 | Pepsi Black 2 L llevando 2 / 2x1 | Chango Mas / MasOnline |        $1.137,25/L | ALERTAR                  |
|       2 | Pepsi Cola 2 L                   | Chango Mas / MasOnline |        $1.705,88/L | ALERTAR                  |
|       3 | Coca-Cola 2,25 L llevando 2      | Vea                    |        $1.882,33/L | ALERTAR                  |
"""

TABLA_MERCADERIA_NORMALIZACION = """| Ranking | Producto                                      | Tienda                 | Normalización | Estado                   |
| ------: | --------------------------------------------- | ---------------------- | ------------: | ------------------------ |
|       1 | Fideos Frescos DIA 500 g                      | DIA Online             |     $2.400/kg | ALERTAR_CONSUMO          |
|       2 | Cerveza Quilmes Bajocero 473 ml               | MasOnline / Chango Mas |   $1.026,85/L | ALERTAR_CONSUMO_+18      |
|       3 | Papel higiénico Family Care 4x30 m llevando 2 | Vea                    |       $8,12/m | ALERTAR_SI_HAY_COBERTURA |
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

    def test_importacion_markdown_toma_precio_normalizado_por_litro(self):
        rows, errores = parsear_tabla_ranking(TABLA_BEBIDAS_PRECIO_NORMALIZADO, "markdown")
        self.assertEqual(rows[0]["precio_normalizado"], "$1.137,25/L")
        self.assertEqual(rows[0]["estado"], "ALERTAR")
        self.assertFalse(errores)

    def test_importacion_markdown_toma_columna_normalizacion(self):
        rows, errores = parsear_tabla_ranking(TABLA_MERCADERIA_NORMALIZACION, "markdown")
        self.assertEqual(rows[0]["precio_normalizado"], "$2.400/kg")
        self.assertEqual(rows[1]["precio_normalizado"], "$1.026,85/L")
        self.assertEqual(rows[2]["precio_normalizado"], "$8,12/m")
        self.assertFalse(errores)

    def test_confirmar_guarda_precio_normalizado_por_litro(self):
        categoria = CategoriaInteres.objects.get(slug="gaseosas")
        preview = previsualizar_ranking(TABLA_BEBIDAS_PRECIO_NORMALIZADO, date(2026, 7, 18), alcance="supermercado")
        datos = {
            "nombre": "Bebidas con senales de alerta",
            "tipo_ranking": LoteRanking.TIPO_SUPERMERCADO_REVENTA,
            "alcance": "supermercado",
            "categoria_id": categoria.id,
            "fecha_referencia": date(2026, 7, 18),
            "origen": "Radar ChatGPT - carga manual",
            "metodologia": "Tabla pegada",
            "estado": LoteRanking.ESTADO_BORRADOR,
            "hash_importacion": preview["hash"],
        }
        lote = confirmar_importacion_ranking(datos, preview["filas"], TABLA_BEBIDAS_PRECIO_NORMALIZADO)
        item = lote.items.order_by("posicion").first()
        self.assertEqual(item.precio_por_litro, Decimal("1137.25"))
        self.assertEqual(item.texto_senal, "ALERTAR")

    def test_confirmar_guarda_normalizacion_por_kg_litro_y_metro(self):
        categoria = CategoriaInteres.objects.get(slug="supermercado-bebidas-mercaderia-revendible")
        preview = previsualizar_ranking(TABLA_MERCADERIA_NORMALIZACION, date(2026, 7, 18), alcance="supermercado")
        datos = {
            "nombre": "Mercaderia con senales de alerta",
            "tipo_ranking": LoteRanking.TIPO_SUPERMERCADO_REVENTA,
            "alcance": "supermercado",
            "categoria_id": categoria.id,
            "fecha_referencia": date(2026, 7, 18),
            "origen": "Radar ChatGPT - carga manual",
            "metodologia": "Tabla pegada",
            "estado": LoteRanking.ESTADO_BORRADOR,
            "hash_importacion": preview["hash"],
        }
        lote = confirmar_importacion_ranking(datos, preview["filas"], TABLA_MERCADERIA_NORMALIZACION)

        fideos = lote.items.get(posicion=1)
        cerveza = lote.items.get(posicion=2)
        papel = lote.items.get(posicion=3)
        self.assertEqual(fideos.precio_por_kg, Decimal("2400.00"))
        self.assertEqual(cerveza.precio_por_litro, Decimal("1026.85"))
        self.assertEqual(papel.precio_por_metro, Decimal("8.12"))

    def test_repara_lote_con_precio_normalizado_desde_texto_original(self):
        categoria = CategoriaInteres.objects.get(slug="gaseosas")
        lote = LoteRanking.objects.create(
            nombre="Bebidas mal importadas",
            tipo_ranking=LoteRanking.TIPO_SUPERMERCADO_REVENTA,
            alcance="supermercado",
            categoria=categoria,
            fecha_referencia=date(2026, 7, 18),
            origen="Radar ChatGPT - carga manual",
            estado=LoteRanking.ESTADO_BORRADOR,
            hash_importacion="demo-precio-normalizado",
            texto_original=TABLA_BEBIDAS_PRECIO_NORMALIZADO,
        )
        ItemRanking.objects.create(lote=lote, posicion=1, nombre_original="Pepsi Black 2 L llevando 2 / 2x1", categoria=categoria, tienda="Chango Mas / MasOnline")
        resumen = reparar_precios_normalizados_lote(lote)
        item = lote.items.get(posicion=1)
        self.assertEqual(resumen["actualizados"], 1)
        self.assertEqual(item.precio_por_litro, Decimal("1137.25"))

    def test_repara_lote_con_columna_normalizacion_desde_texto_original(self):
        categoria = CategoriaInteres.objects.get(slug="supermercado-bebidas-mercaderia-revendible")
        lote = LoteRanking.objects.create(
            nombre="Mercaderia mal importada",
            tipo_ranking=LoteRanking.TIPO_SUPERMERCADO_REVENTA,
            alcance="supermercado",
            categoria=categoria,
            fecha_referencia=date(2026, 7, 18),
            origen="Radar ChatGPT - carga manual",
            estado=LoteRanking.ESTADO_BORRADOR,
            hash_importacion="demo-normalizacion",
            texto_original=TABLA_MERCADERIA_NORMALIZACION,
        )
        ItemRanking.objects.create(lote=lote, posicion=1, nombre_original="Fideos Frescos DIA 500 g", categoria=categoria, tienda="DIA Online")
        ItemRanking.objects.create(lote=lote, posicion=3, nombre_original="Papel higienico Family Care 4x30 m llevando 2", categoria=categoria, tienda="Vea")
        resumen = reparar_precios_normalizados_lote(lote)
        self.assertEqual(resumen["actualizados"], 2)
        self.assertEqual(lote.items.get(posicion=1).precio_por_kg, Decimal("2400.00"))
        self.assertEqual(lote.items.get(posicion=3).precio_por_metro, Decimal("8.12"))

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
