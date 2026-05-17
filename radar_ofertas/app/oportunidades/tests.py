from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, TestCase

from oportunidades.models import CategoriaInteres, FuenteProducto, Oportunidad, PrecioProducto, Producto
from oportunidades.services.clasificacion_service import clasificar_oportunidad
from oportunidades.services.mercado_libre_service import (
    buscar_productos,
    guardar_producto_desde_meli,
    normalizar_resultado_meli,
    sincronizar_busqueda_meli,
)
from oportunidades.services.margen_service import calcular_margen, calcular_porcentaje_margen


def _producto(es_chico_liviano=True, es_fragil=False, vendedor="Vendedor Demo"):
    return SimpleNamespace(
        es_chico_liviano=es_chico_liviano,
        es_fragil=es_fragil,
        vendedor=vendedor,
        fuente=SimpleNamespace(activa=True),
        categoria=SimpleNamespace(activa=True),
    )


class ServiciosComercialesTests(SimpleTestCase):
    def test_calcular_margen(self):
        margen = calcular_margen(
            Decimal("100.00"),
            Decimal("150.00"),
            costo_envio=Decimal("10.00"),
            costo_embalaje=Decimal("5.00"),
            otros_costos=Decimal("5.00"),
        )

        self.assertEqual(margen, Decimal("30.00"))

    def test_calcular_porcentaje_margen(self):
        porcentaje = calcular_porcentaje_margen(Decimal("100.00"), Decimal("35.00"))

        self.assertEqual(porcentaje, Decimal("35.00"))

    def test_clasificar_reventa(self):
        resultado = clasificar_oportunidad(_producto(), Decimal("100.00"), Decimal("145.00"))

        self.assertEqual(resultado["tipo"], "reventa")
        self.assertIn(resultado["riesgo"], ["bajo", "medio"])
        self.assertGreaterEqual(resultado["puntaje"], 75)

    def test_clasificar_afiliado(self):
        resultado = clasificar_oportunidad(_producto(), Decimal("100.00"), Decimal("115.00"))

        self.assertEqual(resultado["tipo"], "afiliado")
        self.assertEqual(resultado["riesgo"], "medio")
        self.assertGreaterEqual(resultado["puntaje"], 50)
        self.assertLessEqual(resultado["puntaje"], 80)

    def test_clasificar_descartar(self):
        resultado = clasificar_oportunidad(_producto(), Decimal("100.00"), Decimal("80.00"))

        self.assertEqual(resultado["tipo"], "descartar")
        self.assertEqual(resultado["riesgo"], "alto")
        self.assertLess(resultado["puntaje"], 50)


class MercadoLibreServiceTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(
            nombre="Organizacion",
            palabra_clave="organizador",
            activa=True,
        )
        self.item_meli = {
            "id": "MLA123",
            "title": "Organizador de cocina",
            "permalink": "https://articulo.mercadolibre.com.ar/MLA-123",
            "price": 10000,
            "currency_id": "ARS",
            "thumbnail": "https://http2.mlstatic.com/thumb.jpg",
            "seller": {"id": 456, "nickname": "Tienda Demo"},
            "condition": "new",
            "sold_quantity": 12,
            "available_quantity": 5,
        }

    def test_normalizar_resultado_meli(self):
        normalizado = normalizar_resultado_meli(self.item_meli)

        self.assertEqual(normalizado["codigo_externo"], "MLA123")
        self.assertEqual(normalizado["titulo"], "Organizador de cocina")
        self.assertEqual(normalizado["precio"], Decimal("10000.00"))
        self.assertEqual(normalizado["condicion"], Producto.CONDICION_NUEVO)
        self.assertEqual(normalizado["vendedor"], "Tienda Demo")
        self.assertTrue(normalizado["disponible"])

    @patch("oportunidades.services.mercado_libre_service.requests.get")
    def test_buscar_productos_maneja_error_http(self, mock_get):
        response = Mock()
        response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = response

        resultado = buscar_productos("organizador", limit=10)

        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["results"], [])
        self.assertIn("Error HTTP", resultado["error"])

    def test_guardar_producto_desde_meli_crea_producto(self):
        normalizado = normalizar_resultado_meli(self.item_meli)

        producto, precio = guardar_producto_desde_meli(normalizado, self.categoria)

        self.assertEqual(Producto.objects.count(), 1)
        self.assertEqual(PrecioProducto.objects.count(), 1)
        self.assertEqual(producto.codigo_externo, "MLA123")
        self.assertEqual(precio.precio, Decimal("10000.00"))

    def test_guardar_producto_desde_meli_no_duplica_producto(self):
        normalizado = normalizar_resultado_meli(self.item_meli)

        guardar_producto_desde_meli(normalizado, self.categoria)
        guardar_producto_desde_meli(normalizado, self.categoria)

        self.assertEqual(Producto.objects.count(), 1)
        self.assertEqual(PrecioProducto.objects.count(), 1)

    @patch("oportunidades.services.mercado_libre_service.buscar_productos")
    def test_sincronizar_busqueda_meli_crea_oportunidades(self, mock_buscar):
        mock_buscar.return_value = {
            "ok": True,
            "results": [self.item_meli],
            "paging": {},
            "error": None,
            "site_id": "MLA",
        }

        resumen = sincronizar_busqueda_meli("organizador", categoria=self.categoria, limit=1)

        self.assertEqual(resumen["procesados"], 1)
        self.assertEqual(resumen["creados"], 1)
        self.assertEqual(resumen["errores"], 0)
        self.assertEqual(FuenteProducto.objects.filter(nombre="Mercado Libre").count(), 1)
        self.assertEqual(Oportunidad.objects.count(), 1)
