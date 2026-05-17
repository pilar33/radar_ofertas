import os
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from oportunidades.models import CategoriaInteres, FuenteProducto, MercadoLibreToken, Oportunidad, PrecioProducto, Producto
from oportunidades.services.clasificacion_service import clasificar_oportunidad
from oportunidades.services.mercado_libre_service import (
    buscar_productos,
    get_headers,
    guardar_producto_desde_meli,
    normalizar_resultado_meli,
    preparar_link_afiliado,
    request_meli,
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

    @patch("oportunidades.services.mercado_libre_service.requests.request")
    def test_buscar_productos_maneja_error_http(self, mock_request):
        response = Mock()
        response.status_code = 500
        response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_request.return_value = response

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
            "status_code": 200,
            "requires_token": False,
            "forbidden": False,
            "uso_token": False,
        }

        resumen = sincronizar_busqueda_meli("organizador", categoria=self.categoria, limit=1)

        self.assertEqual(resumen["procesados"], 1)
        self.assertEqual(resumen["creados"], 1)
        self.assertEqual(resumen["errores"], 0)
        self.assertEqual(FuenteProducto.objects.filter(nombre="Mercado Libre").count(), 1)
        self.assertEqual(Oportunidad.objects.count(), 1)

    @patch.dict(os.environ, {"MELI_ACCESS_TOKEN": ""}, clear=False)
    def test_get_headers_sin_token(self):
        headers = get_headers(use_auth=True)

        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept-Language"], "es-AR,es;q=0.9")
        self.assertNotIn("Authorization", headers)

    @patch.dict(os.environ, {"MELI_ACCESS_TOKEN": "token-demo"}, clear=False)
    def test_get_headers_con_token(self):
        headers = get_headers(use_auth=True)

        self.assertEqual(headers["Authorization"], "Bearer token-demo")

    @patch("oportunidades.services.mercado_libre_service.requests.request")
    def test_request_meli_403(self, mock_request):
        response = Mock()
        response.status_code = 403
        mock_request.return_value = response

        resultado = request_meli("GET", "/sites/MLA/search", use_auth=False)

        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["status_code"], 403)
        self.assertTrue(resultado["forbidden"])
        self.assertTrue(resultado["requires_token"])

    @patch("oportunidades.services.mercado_libre_service.request_meli")
    def test_buscar_productos_403_devuelve_requires_token(self, mock_request_meli):
        mock_request_meli.return_value = {
            "ok": False,
            "status_code": 403,
            "data": None,
            "error": "Mercado Libre devolvio 403 Forbidden.",
            "requires_token": True,
            "forbidden": True,
        }

        resultado = buscar_productos("organizador", usar_token_si_existe=False)

        self.assertFalse(resultado["ok"])
        self.assertTrue(resultado["requires_token"])
        self.assertTrue(resultado["forbidden"])
        self.assertIn("MELI_ACCESS_TOKEN", resultado["error"])

    def test_normalizar_resultado_meli_campos_faltantes(self):
        normalizado = normalizar_resultado_meli({"id": "MLA999"})

        self.assertEqual(normalizado["codigo_externo"], "MLA999")
        self.assertEqual(normalizado["titulo"], "Producto sin titulo")
        self.assertEqual(normalizado["precio"], Decimal("0.00"))
        self.assertEqual(normalizado["condicion"], Producto.CONDICION_DESCONOCIDO)
        self.assertFalse(normalizado["disponible"])

    @patch.dict(os.environ, {"MELI_AFFILIATE_BASE_URL": "", "MELI_AFFILIATE_TAG": ""}, clear=False)
    def test_preparar_link_afiliado_sin_configuracion(self):
        fuente = FuenteProducto.objects.create(nombre="Manual", tipo=FuenteProducto.TIPO_MANUAL)
        producto = Producto.objects.create(
            fuente=fuente,
            categoria=self.categoria,
            titulo="Producto demo",
            url="https://example.com/producto",
            condicion=Producto.CONDICION_NUEVO,
        )

        resultado = preparar_link_afiliado(producto)

        self.assertEqual(resultado["url"], producto.url)
        self.assertFalse(resultado["configurado"])
        self.assertIn("Link afiliado no configurado", resultado["mensaje"])

    @patch.dict(os.environ, {"MELI_ACCESS_TOKEN": "token-env"}, clear=False)
    def test_obtener_token_activo_prioriza_db(self):
        from oportunidades.services.mercado_libre_service import obtener_token_activo

        MercadoLibreToken.objects.create(
            access_token="token-db",
            refresh_token="refresh-db",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
            activo=True,
        )

        self.assertEqual(obtener_token_activo(), "token-db")

    @patch("oportunidades.management.commands.diagnosticar_meli.buscar_productos")
    @patch.dict(
        os.environ,
        {
            "MELI_CLIENT_ID": "client-demo",
            "MELI_CLIENT_SECRET": "secret-demo",
            "MELI_ACCESS_TOKEN": "token-demo",
        },
        clear=False,
    )
    def test_diagnostico_no_muestra_secretos(self, mock_buscar):
        mock_buscar.return_value = {
            "ok": False,
            "status_code": 403,
            "error": "Forbidden",
            "forbidden": True,
        }
        salida = StringIO()

        call_command("diagnosticar_meli", stdout=salida)
        texto = salida.getvalue()

        self.assertIn("MELI_CLIENT_SECRET configurado: si", texto)
        self.assertIn("MELI_ACCESS_TOKEN configurado: si", texto)
        self.assertNotIn("secret-demo", texto)
        self.assertNotIn("token-demo", texto)
