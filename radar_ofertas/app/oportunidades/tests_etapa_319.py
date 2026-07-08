import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase

from oportunidades.models import (
    CandidatoCompra, CategoriaInteres, CompraProducto, FuenteWeb, PrecioFuente, Producto,
    ProductoCanonico, ProductoFuente, PublicacionReventa, ResultadoComercialProducto, VentaProducto,
)
from oportunidades.services.dataset_export_service import exportar_dataset_productos_csv
from oportunidades.services.seguimiento_comercial_service import (
    crear_candidato_desde_producto, descartar_candidato, recalcular_resultado_comercial,
    registrar_compra, registrar_publicacion, registrar_venta,
)


class Etapa319SeguimientoComercialTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(nombre="Comercial", palabra_clave="comercial")
        self.fuente = FuenteWeb.objects.create(nombre="Fuente comercial", url_base="https://comercial.example/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE)
        self.canonico = ProductoCanonico.objects.create(nombre_normalizado="producto comercial", categoria=self.categoria)
        self.producto = ProductoFuente.objects.create(
            producto_canonico=self.canonico, fuente_web=self.fuente, titulo_original="Producto comercial",
            url_producto="https://comercial.example/producto", condicion=Producto.CONDICION_NUEVO,
            score_comercial=80, score_demanda_actual=75,
        )
        PrecioFuente.objects.create(
            producto_fuente=self.producto, precio=Decimal("1000"), precio_oportunidad=Decimal("1000"),
            precio_lista=Decimal("1300"), precio_transferencia=Decimal("1000"), origen_dato=PrecioFuente.ORIGEN_MANUAL,
        )
        self.candidato, _ = crear_candidato_desde_producto(self.producto, "Prueba comercial")

    def _datos_compra(self, cantidad=2, precio="1000"):
        return {"fecha_compra": date(2026, 6, 1), "cantidad_comprada": cantidad, "precio_unitario_compra": Decimal(precio), "costo_envio": Decimal("100"), "costo_comision": Decimal("0"), "otros_costos": Decimal("0"), "estado": CompraProducto.ESTADO_CONFIRMADA}

    def _compra(self, cantidad=2, precio="1000"):
        return registrar_compra(self.candidato, self._datos_compra(cantidad, precio))

    def _datos_venta(self, cantidad=1, precio="1600"):
        return {"fecha_venta": date(2026, 6, 5), "cantidad_vendida": cantidad, "precio_unitario_venta": Decimal(precio), "comision_venta": Decimal("100"), "costo_envio_venta": Decimal("0"), "otros_costos_venta": Decimal("0"), "canal_venta": PublicacionReventa.CANAL_LOCAL, "estado": VentaProducto.ESTADO_CONFIRMADA}

    def test_crear_compra_producto(self):
        self.assertEqual(self._compra().cantidad_comprada, 2)

    def test_crear_publicacion_reventa(self):
        compra = self._compra()
        publicacion = registrar_publicacion(compra, {"canal": "local", "titulo_publicacion": "Venta", "fecha_publicacion": date(2026, 6, 2), "precio_publicado_unitario": Decimal("1600"), "cantidad_publicada": 2, "estado": "publicada"})
        self.assertEqual(publicacion.compra, compra)

    def test_crear_venta_producto(self):
        self.assertEqual(registrar_venta(self._compra(), self._datos_venta()).cantidad_vendida, 1)

    def test_crear_resultado_comercial_producto(self):
        self.assertTrue(ResultadoComercialProducto.objects.filter(candidato=self.candidato).exists())

    def test_compra_calcula_costo_total(self):
        self.assertEqual(self._compra().costo_total, Decimal("2100"))

    def test_compra_calcula_costo_unitario_real(self):
        self.assertEqual(self._compra().costo_unitario_real, Decimal("1050"))

    def test_venta_calcula_ingreso_bruto(self):
        self.assertEqual(registrar_venta(self._compra(), self._datos_venta()).ingreso_bruto, Decimal("1600"))

    def test_venta_calcula_ganancia_neta(self):
        self.assertEqual(registrar_venta(self._compra(), self._datos_venta()).ganancia_neta, Decimal("450"))

    def test_venta_calcula_margen_pct(self):
        self.assertGreater(registrar_venta(self._compra(), self._datos_venta()).margen_pct, 40)

    def test_no_permite_vender_mas_de_lo_disponible(self):
        with self.assertRaises(ValidationError):
            registrar_venta(self._compra(cantidad=1), self._datos_venta(cantidad=2))

    def test_crear_candidato_desde_producto(self):
        self.assertEqual(self.candidato.score_comercial_detectado, 80)
        self.assertEqual(self.candidato.prioridad, CandidatoCompra.PRIORIDAD_ALTA)

    def test_registrar_compra_actualiza_candidato(self):
        self._compra()
        self.candidato.refresh_from_db()
        self.assertEqual(self.candidato.estado, CandidatoCompra.ESTADO_COMPRADO)

    def test_registrar_venta_recalcula_resultado(self):
        registrar_venta(self._compra(), self._datos_venta())
        self.candidato.resultado_comercial.refresh_from_db()
        self.assertEqual(self.candidato.resultado_comercial.cantidad_vendida_total, 1)

    def test_recalcular_resultado_comercial_vendido_con_ganancia(self):
        registrar_venta(self._compra(cantidad=1), self._datos_venta(precio="1800"))
        self.assertEqual(recalcular_resultado_comercial(self.candidato).estado_resultado, ResultadoComercialProducto.ESTADO_VENDIDO_CON_GANANCIA)

    def test_recalcular_resultado_comercial_vendido_con_perdida(self):
        registrar_venta(self._compra(cantidad=1), self._datos_venta(precio="900"))
        self.assertEqual(recalcular_resultado_comercial(self.candidato).estado_resultado, ResultadoComercialProducto.ESTADO_VENDIDO_CON_PERDIDA)

    def test_descartar_candidato(self):
        descartar_candidato(self.candidato, "No conviene")
        self.assertEqual(self.candidato.estado, CandidatoCompra.ESTADO_DESCARTADO)

    def test_comercial_dashboard_carga(self):
        self.assertEqual(Client(HTTP_HOST="localhost").get("/comercial/dashboard/").status_code, 200)

    def test_comercial_candidatos_carga(self):
        self.assertEqual(Client(HTTP_HOST="localhost").get("/comercial/candidatos/").status_code, 200)

    def test_detalle_candidato_carga(self):
        self.assertEqual(Client(HTTP_HOST="localhost").get(f"/comercial/candidatos/{self.candidato.id}/").status_code, 200)

    def test_registrar_compra_view(self):
        response = Client(HTTP_HOST="localhost").post(f"/comercial/candidatos/{self.candidato.id}/registrar-compra/", {"fecha_compra": "2026-06-01", "cantidad_comprada": 1, "precio_unitario_compra": "1000", "costo_envio": "0", "costo_comision": "0", "otros_costos": "0", "estado": "confirmada"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.candidato.compras.exists())

    def test_registrar_venta_view(self):
        compra = self._compra(cantidad=1)
        response = Client(HTTP_HOST="localhost").post(f"/comercial/compras/{compra.id}/registrar-venta/", {"fecha_venta": "2026-06-05", "cantidad_vendida": 1, "precio_unitario_venta": "1500", "comision_venta": "0", "costo_envio_venta": "0", "otros_costos_venta": "0", "canal_venta": "local", "estado": "confirmada"})
        self.assertEqual(response.status_code, 302)

    def test_export_dataset_incluye_resultado_comercial(self):
        self.assertIn("estado_resultado_comercial", exportar_dataset_productos_csv().getvalue().splitlines()[0])

    def _fila_dataset(self):
        return next(csv.DictReader(exportar_dataset_productos_csv().getvalue().splitlines()))

    def test_resultado_positivo_true_si_ganancia(self):
        registrar_venta(self._compra(cantidad=1), self._datos_venta(precio="1800"))
        self.assertEqual(self._fila_dataset()["resultado_positivo"], "True")

    def test_resultado_positivo_false_si_perdida(self):
        registrar_venta(self._compra(cantidad=1), self._datos_venta(precio="800"))
        self.assertEqual(self._fila_dataset()["resultado_positivo"], "False")

    def test_recalcular_resultados_comerciales_command(self):
        salida = StringIO()
        call_command("recalcular_resultados_comerciales", "--candidato-id", self.candidato.id, stdout=salida)
        self.assertIn("recalculados: 1", salida.getvalue())

    def test_listar_resultados_comerciales_command(self):
        salida = StringIO()
        call_command("listar_resultados_comerciales", "--limite", 20, stdout=salida)
        self.assertIn("Resultados mostrados", salida.getvalue())

    def test_manual_operativo_incluye_seguimiento_comercial(self):
        manual = Path(__file__).resolve().parents[1] / "docs" / "manual_operativo_radar.md"
        self.assertIn("Seguimiento comercial real", manual.read_text(encoding="utf-8"))
