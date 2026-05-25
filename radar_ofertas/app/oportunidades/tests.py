import os
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from oportunidades.models import (
    CategoriaInteres,
    ConectorFuente,
    DecisionTecnica,
    DetalleImportacionProducto,
    EjecucionConector,
    FuenteProducto,
    FuenteWeb,
    ImportacionProductos,
    MercadoLibreToken,
    Oportunidad,
    PoliticaExtraccionFuente,
    PrecioFuente,
    PrecioProducto,
    Producto,
    ProductoCanonico,
    ProductoFuente,
)
from oportunidades.services.clasificacion_service import clasificar_oportunidad
from oportunidades.services.mercado_libre_service import (
    buscar_productos,
    diagnosticar_endpoints_meli,
    get_headers,
    guardar_producto_desde_meli,
    interpretar_diagnostico_meli,
    normalizar_resultado_meli,
    preparar_link_afiliado,
    request_meli,
    sincronizar_busqueda_meli,
)
from oportunidades.services.margen_service import calcular_margen, calcular_porcentaje_margen
from oportunidades.services.fuentes_service import fuente_permite_automatizacion
from oportunidades.services.normalizacion_service import normalizar_texto_producto
from oportunidades.services.importacion_service import (
    crear_producto_desde_carga_url,
    detectar_tipo_archivo,
    normalizar_columnas_importacion,
    parsear_decimal,
    procesar_importacion,
)
from oportunidades.services.conectores_service import validar_conector_segun_politica
from oportunidades.services.conector_catalogo_service import (
    ejecutar_conector_catalogo,
    validar_conector_catalogo,
)
from oportunidades.services.storage_service import diagnosticar_storage_config


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

    def test_users_me_ok_search_403_interpretacion(self):
        resultados = [
            {"nombre": "users/me", "ok": True, "status_code": 200},
            {"nombre": "search con token", "ok": False, "status_code": 403},
        ]

        interpretacion = interpretar_diagnostico_meli(resultados)

        self.assertIn("OAuth y token funcionan", interpretacion)
        self.assertIn("endpoint de busqueda general", interpretacion)

    def test_users_me_401_interpretacion(self):
        resultados = [
            {"nombre": "users/me", "ok": False, "status_code": 401},
            {"nombre": "search con token", "ok": False, "status_code": 403},
        ]

        interpretacion = interpretar_diagnostico_meli(resultados)

        self.assertIn("token es invalido o vencido", interpretacion)

    def test_categories_ok_search_403(self):
        resultados = [
            {"nombre": "users/me", "ok": False, "status_code": None},
            {"nombre": "sites categories", "ok": True, "status_code": 200},
            {"nombre": "search con token", "ok": False, "status_code": 403},
        ]

        interpretacion = interpretar_diagnostico_meli(resultados)

        self.assertIn("conectividad con Mercado Libre funciona", interpretacion)
        self.assertIn("busqueda de productos esta restringida", interpretacion)

    @patch.dict(os.environ, {"MELI_ACCESS_TOKEN": "token-super-secreto"}, clear=False)
    @patch("oportunidades.services.mercado_libre_service.request_meli")
    def test_no_expone_token_en_respuesta(self, mock_request_meli):
        mock_request_meli.side_effect = [
            {"ok": True, "status_code": 200, "data": {"id": 1}, "error": None, "response_text": ""},
            {"ok": True, "status_code": 200, "data": [], "error": None, "response_text": ""},
            {"ok": False, "status_code": 403, "error": "Forbidden", "response_text": "forbidden"},
            {"ok": False, "status_code": 403, "error": "Forbidden", "response_text": "forbidden"},
            {"ok": True, "status_code": 200, "data": {"id": "MLA"}, "error": None, "response_text": ""},
        ]

        diagnostico = diagnosticar_endpoints_meli()
        texto = str(diagnostico)

        self.assertNotIn("token-super-secreto", texto)

    @patch("oportunidades.services.mercado_libre_service.requests.request")
    def test_response_error_limitado_500_caracteres(self, mock_request):
        response = Mock()
        response.status_code = 403
        response.text = "x" * 700
        mock_request.return_value = response

        resultado = request_meli("GET", "/sites/MLA/search", use_auth=False)

        self.assertEqual(resultado["status_code"], 403)
        self.assertEqual(len(resultado["response_text"]), 500)


class MultifuenteTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(
            nombre="Hogar",
            palabra_clave="hogar",
            activa=True,
        )

    def test_crear_fuente_web(self):
        fuente = FuenteWeb.objects.create(
            nombre="Proveedor Demo",
            url_base="https://example.com",
            tipo_fuente=FuenteWeb.TIPO_EXCEL_CSV,
        )

        self.assertEqual(fuente.nombre, "Proveedor Demo")
        self.assertTrue(fuente.activa)

    def test_politica_extraccion_semaforo(self):
        fuente = FuenteWeb.objects.create(
            nombre="Fuente politica",
            url_base="https://example.com/politica",
            tipo_fuente=FuenteWeb.TIPO_API_OFICIAL,
        )
        politica = PoliticaExtraccionFuente.objects.create(
            fuente=fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_VERDE,
            metodo_preferido=PoliticaExtraccionFuente.METODO_API_OFICIAL,
            tiene_api=True,
        )

        self.assertEqual(politica.semaforo, PoliticaExtraccionFuente.SEMAFORO_VERDE)

    def test_fuente_roja_no_permite_automatizacion(self):
        fuente = FuenteWeb.objects.create(
            nombre="Fuente roja",
            url_base="https://example.com/roja",
            tipo_fuente=FuenteWeb.TIPO_MARKETPLACE,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_ROJO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_NO_PERMITIDO,
        )

        self.assertFalse(fuente_permite_automatizacion(fuente))

    def test_fuente_verde_permite_automatizacion(self):
        fuente = FuenteWeb.objects.create(
            nombre="Fuente verde",
            url_base="https://example.com/verde",
            tipo_fuente=FuenteWeb.TIPO_EXCEL_CSV,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_VERDE,
            metodo_preferido=PoliticaExtraccionFuente.METODO_CSV_EXCEL,
        )

        self.assertTrue(fuente_permite_automatizacion(fuente))

    def test_normalizar_texto_producto(self):
        texto = normalizar_texto_producto("  Organizador Cocina 3-Pisos!! ")

        self.assertEqual(texto, "organizador cocina 3 pisos")

    def test_crear_decision_tecnica(self):
        decision = DecisionTecnica.objects.create(
            titulo="Decision demo",
            categoria=DecisionTecnica.CATEGORIA_DATOS,
            descripcion="Descripcion",
            decision="Decidir algo",
        )

        self.assertEqual(decision.categoria, DecisionTecnica.CATEGORIA_DATOS)

    def test_inicializar_multifuente_crea_mercado_libre_documentado(self):
        call_command("inicializar_multifuente")

        mercado_libre = FuenteWeb.objects.get(nombre="Mercado Libre")
        self.assertEqual(mercado_libre.politica_extraccion.semaforo, PoliticaExtraccionFuente.SEMAFORO_ROJO)
        self.assertTrue(
            DecisionTecnica.objects.filter(
                titulo="Mercado Libre no sera fuente automatica principal en esta etapa"
            ).exists()
        )


class ImportacionMultifuenteTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(
            nombre="Organizacion",
            palabra_clave="organizador",
            activa=True,
        )
        self.fuente = FuenteWeb.objects.create(
            nombre="Mayorista Demo",
            url_base="https://example.com",
            tipo_fuente=FuenteWeb.TIPO_EXCEL_CSV,
            activa=True,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_VERDE,
            metodo_preferido=PoliticaExtraccionFuente.METODO_CSV_EXCEL,
        )

    def _crear_importacion(self, contenido, nombre="productos.csv"):
        archivo = SimpleUploadedFile(nombre, contenido.encode("utf-8"), content_type="text/csv")
        return ImportacionProductos.objects.create(
            fuente_web=self.fuente,
            archivo=archivo,
            tipo_archivo=detectar_tipo_archivo(archivo),
        )

    def test_detectar_tipo_archivo_csv(self):
        archivo = SimpleNamespace(name="lista.csv")

        self.assertEqual(detectar_tipo_archivo(archivo), ImportacionProductos.TIPO_CSV)

    def test_parsear_decimal_formato_argentino(self):
        self.assertEqual(parsear_decimal("$ 1.200,50"), Decimal("1200.50"))
        self.assertEqual(parsear_decimal("1200.50"), Decimal("1200.50"))

    def test_normalizar_columnas_importacion(self):
        df = pd.DataFrame([{"Nombre Producto": "Organizador", "Importe": "1200", "SKU": "A1"}])
        normalizado = normalizar_columnas_importacion(df)

        self.assertIn("titulo", normalizado.columns)
        self.assertIn("precio", normalizado.columns)
        self.assertIn("codigo_externo", normalizado.columns)

    def test_importacion_crea_producto_fuente(self):
        importacion = self._crear_importacion("codigo_externo,titulo,precio,categoria\nSKU1,Organizador,1200,Organizacion\n")
        procesar_importacion(importacion, {"categoria_default": self.categoria})

        importacion.refresh_from_db()
        self.assertEqual(importacion.productos_creados, 1)
        self.assertTrue(ProductoFuente.objects.filter(codigo_externo="SKU1").exists())
        self.assertTrue(ProductoCanonico.objects.filter(nombre_normalizado="organizador").exists())

    def test_importacion_no_duplica_producto_fuente_por_codigo(self):
        contenido = "codigo_externo,titulo,precio,categoria\nSKU1,Organizador,1200,Organizacion\n"
        procesar_importacion(self._crear_importacion(contenido), {"categoria_default": self.categoria})
        procesar_importacion(self._crear_importacion(contenido, "productos_2.csv"), {"categoria_default": self.categoria})

        self.assertEqual(ProductoFuente.objects.filter(codigo_externo="SKU1").count(), 1)

    def test_importacion_crea_precio_si_cambia(self):
        procesar_importacion(
            self._crear_importacion("codigo_externo,titulo,precio,categoria\nSKU1,Organizador,1200,Organizacion\n"),
            {"categoria_default": self.categoria},
        )
        procesar_importacion(
            self._crear_importacion("codigo_externo,titulo,precio,categoria\nSKU1,Organizador,1300,Organizacion\n", "b.csv"),
            {"categoria_default": self.categoria},
        )

        producto = ProductoFuente.objects.get(codigo_externo="SKU1")
        self.assertEqual(producto.precios_fuente.count(), 2)

    def test_importacion_no_crea_precio_duplicado_si_no_cambio(self):
        contenido = "codigo_externo,titulo,precio,categoria\nSKU1,Organizador,1200,Organizacion\n"
        procesar_importacion(self._crear_importacion(contenido), {"categoria_default": self.categoria})
        procesar_importacion(self._crear_importacion(contenido, "b.csv"), {"categoria_default": self.categoria})

        producto = ProductoFuente.objects.get(codigo_externo="SKU1")
        self.assertEqual(producto.precios_fuente.count(), 1)

    @patch("requests.get")
    def test_carga_url_no_hace_request_externo(self, requests_get):
        resultado = crear_producto_desde_carga_url(
            {
                "fuente_web": self.fuente,
                "url_producto": "https://example.com/producto",
                "titulo": "Organizador URL",
                "precio": "1200",
                "categoria": self.categoria,
                "moneda": "ARS",
            }
        )

        self.assertTrue(resultado["ok"])
        requests_get.assert_not_called()

    def test_carga_url_crea_producto_precio_evaluacion(self):
        resultado = crear_producto_desde_carga_url(
            {
                "fuente_web": self.fuente,
                "url_producto": "https://example.com/producto",
                "titulo": "Organizador URL",
                "precio": "1200",
                "categoria": self.categoria,
                "moneda": "ARS",
                "es_chico_liviano": True,
                "es_fragil": False,
            }
        )

        self.assertTrue(resultado["ok"])
        self.assertIsNotNone(resultado["precio_fuente"])
        self.assertIsNotNone(resultado["evaluacion"])

    def test_importacion_con_fila_invalida_registra_error_y_continua(self):
        contenido = "codigo_externo,titulo,precio,categoria\nSKU1,Organizador,1200,Organizacion\nSKU2,,abc,Organizacion\n"
        importacion = self._crear_importacion(contenido)
        procesar_importacion(importacion, {"categoria_default": self.categoria})

        importacion.refresh_from_db()
        self.assertEqual(importacion.productos_creados, 1)
        self.assertEqual(importacion.errores, 1)
        self.assertEqual(DetalleImportacionProducto.objects.filter(importacion=importacion).count(), 2)


class StorageConfigTests(SimpleTestCase):
    @override_settings(USE_EXTERNAL_STORAGE=False, RENDER=False, MEDIA_URL="/media/")
    def test_use_external_storage_false_usa_media_local(self):
        diagnostico = diagnosticar_storage_config()

        self.assertFalse(diagnostico["use_external_storage"])
        self.assertEqual(diagnostico["media_url"], "/media/")

    @override_settings(
        USE_EXTERNAL_STORAGE=True,
        RENDER=False,
        MEDIA_URL="/media/",
        AWS_STORAGE_BUCKET_NAME="bucket-demo",
        AWS_ACCESS_KEY_ID="access-secret",
        AWS_SECRET_ACCESS_KEY="super-secret",
        AWS_S3_ENDPOINT_URL="https://storage.example.com",
        STORAGE_BACKEND="s3",
    )
    def test_storage_diagnostico_no_expone_secretos(self):
        diagnostico = diagnosticar_storage_config()
        texto = str(diagnostico)

        self.assertTrue(diagnostico["access_key_configurada"])
        self.assertNotIn("access-secret", texto)
        self.assertNotIn("super-secret", texto)

    @override_settings(USE_EXTERNAL_STORAGE=False, RENDER=True, MEDIA_URL="/media/")
    def test_diagnostico_storage_render_sin_externo_advierte(self):
        diagnostico = diagnosticar_storage_config()

        self.assertTrue(diagnostico["advertencias"])
        self.assertIn("filesystem efimero", diagnostico["advertencias"][0])


class ConectoresTests(TestCase):
    def setUp(self):
        self.fuente_verde = FuenteWeb.objects.create(
            nombre="API Verde",
            url_base="https://example.com/api",
            tipo_fuente=FuenteWeb.TIPO_API_OFICIAL,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente_verde,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_VERDE,
            metodo_preferido=PoliticaExtraccionFuente.METODO_API_OFICIAL,
            tiene_api=True,
        )
        self.fuente_roja = FuenteWeb.objects.create(
            nombre="Roja",
            url_base="https://example.com/roja",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente_roja,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_ROJO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_NO_PERMITIDO,
        )
        self.fuente_amarilla = FuenteWeb.objects.create(
            nombre="Amarilla",
            url_base="https://example.com/amarilla",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente_amarilla,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_PENDIENTE_REVISION,
            permite_scraping=True,
        )

    def test_crear_conector_fuente(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="API oficial",
            tipo_conector=ConectorFuente.TIPO_API_OFICIAL,
            estado=ConectorFuente.ESTADO_ACTIVO,
        )

        self.assertEqual(conector.fuente_web, self.fuente_verde)

    def test_fuente_roja_bloquea_scraping(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_roja,
            nombre="Scraping",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
        )
        validacion = validar_conector_segun_politica(conector)

        self.assertFalse(validacion["valido"])
        self.assertEqual(validacion["nivel"], "bloqueado")

    def test_fuente_verde_api_ok(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="API",
            tipo_conector=ConectorFuente.TIPO_API_OFICIAL,
            estado=ConectorFuente.ESTADO_ACTIVO,
        )
        validacion = validar_conector_segun_politica(conector)

        self.assertTrue(validacion["valido"])
        self.assertEqual(validacion["nivel"], "ok")

    def test_fuente_amarilla_scraping_requiere_revision(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_amarilla,
            nombre="Scraping revisable",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_BORRADOR,
        )
        validacion = validar_conector_segun_politica(conector)

        self.assertTrue(validacion["valido"])
        self.assertEqual(validacion["nivel"], "advertencia")

    def test_inicializar_conectores_base_no_duplica(self):
        call_command("inicializar_multifuente")
        call_command("inicializar_conectores_base")
        primera_cantidad = ConectorFuente.objects.count()
        call_command("inicializar_conectores_base")

        self.assertEqual(ConectorFuente.objects.count(), primera_cantidad)

    def test_importacion_puede_vincular_conector(self):
        categoria = CategoriaInteres.objects.create(nombre="Demo", palabra_clave="demo")
        fuente = FuenteWeb.objects.create(
            nombre="CSV Fuente",
            url_base="https://example.com/csv",
            tipo_fuente=FuenteWeb.TIPO_EXCEL_CSV,
        )
        ConectorFuente.objects.create(
            fuente_web=fuente,
            nombre="Importacion CSV/Excel manual",
            tipo_conector=ConectorFuente.TIPO_CSV_MANUAL,
            estado=ConectorFuente.ESTADO_ACTIVO,
        )
        archivo = SimpleUploadedFile(
            "productos.csv",
            b"codigo_externo,titulo,precio,categoria\nSKU1,Producto demo,1200,Demo\n",
            content_type="text/csv",
        )
        importacion = ImportacionProductos.objects.create(
            fuente_web=fuente,
            archivo=archivo,
            tipo_archivo=ImportacionProductos.TIPO_CSV,
        )
        procesar_importacion(importacion, {"categoria_default": categoria})

        importacion.refresh_from_db()
        self.assertIsNotNone(importacion.conector)


class StorageRealTests(SimpleTestCase):
    def test_probar_storage_crea_y_elimina_archivo(self):
        from oportunidades.services.storage_service import probar_storage

        resultado = probar_storage()

        self.assertTrue(resultado["ok"])

    @override_settings(
        USE_EXTERNAL_STORAGE=True,
        RENDER=True,
        MEDIA_URL="/media/",
        AWS_STORAGE_BUCKET_NAME="",
        AWS_ACCESS_KEY_ID="",
        AWS_SECRET_ACCESS_KEY="",
        AWS_S3_ENDPOINT_URL="",
        AWS_S3_REGION_NAME="",
        STORAGE_BACKEND="s3",
    )
    def test_diagnostico_storage_external_config_incompleta(self):
        diagnostico = diagnosticar_storage_config()

        self.assertTrue(diagnostico["advertencias"])
        self.assertIn("STORAGE_BUCKET_NAME", diagnostico["advertencias"][0])


class ConectorCatalogoTests(TestCase):
    def setUp(self):
        self.categoria = CategoriaInteres.objects.create(nombre="Demo catalogo", palabra_clave="demo")
        self.fuente_verde = FuenteWeb.objects.create(
            nombre="Catalogo Verde",
            url_base="https://example.com/",
            tipo_fuente=FuenteWeb.TIPO_EXCEL_CSV,
            activa=True,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente_verde,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_VERDE,
            metodo_preferido=PoliticaExtraccionFuente.METODO_CSV_EXCEL,
        )
        self.fuente_roja = FuenteWeb.objects.create(
            nombre="Catalogo Rojo",
            url_base="https://example.com/rojo",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            activa=True,
        )
        PoliticaExtraccionFuente.objects.create(
            fuente=self.fuente_roja,
            semaforo=PoliticaExtraccionFuente.SEMAFORO_ROJO,
            metodo_preferido=PoliticaExtraccionFuente.METODO_NO_PERMITIDO,
        )

    def test_validar_conector_catalogo_csv_manual_ok(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="CSV manual",
            tipo_conector=ConectorFuente.TIPO_CSV_MANUAL,
            estado=ConectorFuente.ESTADO_ACTIVO,
            fuente_autorizo_uso=True,
        )

        self.assertEqual(validar_conector_catalogo(conector)["nivel"], "ok")

    def test_validar_conector_catalogo_bloquea_scraping(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="Scraping",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
        )

        self.assertEqual(validar_conector_catalogo(conector)["nivel"], "bloqueado")

    def test_validar_conector_catalogo_remoto_sin_url_error(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="CSV remoto",
            tipo_conector=ConectorFuente.TIPO_CSV_REMOTO,
            requiere_descarga=True,
        )

        self.assertFalse(validar_conector_catalogo(conector)["valido"])

    def test_validar_conector_catalogo_fuente_roja_sin_autorizacion_bloqueado(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_roja,
            nombre="CSV remoto rojo",
            tipo_conector=ConectorFuente.TIPO_CSV_REMOTO,
            requiere_descarga=True,
            url_recurso="https://example.com/catalogo.csv",
            formato_recurso=ConectorFuente.FORMATO_CSV,
        )

        self.assertEqual(validar_conector_catalogo(conector)["nivel"], "bloqueado")

    def test_crear_conector_catalogo_demo_no_duplica(self):
        call_command("crear_conector_catalogo_demo")
        primera_cantidad = ConectorFuente.objects.filter(nombre="Conector CSV Demo").count()
        call_command("crear_conector_catalogo_demo")

        self.assertEqual(ConectorFuente.objects.filter(nombre="Conector CSV Demo").count(), primera_cantidad)

    def test_ejecutar_conector_manual_sin_importacion_pendiente_mensaje_claro(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="CSV manual",
            tipo_conector=ConectorFuente.TIPO_CSV_MANUAL,
            estado=ConectorFuente.ESTADO_ACTIVO,
            fuente_autorizo_uso=True,
        )
        ejecucion = ejecutar_conector_catalogo(conector)

        self.assertEqual(ejecucion.errores, 0)
        self.assertIn("sin importaciones pendientes", ejecucion.mensaje)

    @patch("oportunidades.services.conector_catalogo_service.requests.get")
    def test_ejecutar_conector_remoto_no_acepta_html(self, requests_get):
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/html"}
        response.iter_content.return_value = [b"<html></html>"]
        requests_get.return_value = response
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="HTML remoto",
            tipo_conector=ConectorFuente.TIPO_CSV_REMOTO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_descarga=True,
            fuente_autorizo_uso=True,
            url_recurso="https://example.com/catalogo.csv",
            formato_recurso=ConectorFuente.FORMATO_CSV,
        )
        ejecucion = ejecutar_conector_catalogo(conector)

        self.assertEqual(ejecucion.errores, 1)
        self.assertIn("HTML", ejecucion.mensaje)

    @patch("oportunidades.services.conector_catalogo_service.requests.get")
    def test_ejecutar_conector_remoto_crea_importacion_con_mock(self, requests_get):
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "text/csv"}
        response.iter_content.return_value = [b"codigo_externo,titulo,precio,categoria\nSKU1,Producto demo,1200,Demo catalogo\n"]
        requests_get.return_value = response
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="CSV remoto",
            tipo_conector=ConectorFuente.TIPO_CSV_REMOTO,
            estado=ConectorFuente.ESTADO_ACTIVO,
            requiere_descarga=True,
            fuente_autorizo_uso=True,
            url_recurso="https://example.com/catalogo.csv",
            formato_recurso=ConectorFuente.FORMATO_CSV,
        )
        ejecucion = ejecutar_conector_catalogo(conector)

        self.assertEqual(ejecucion.errores, 0)
        self.assertEqual(ImportacionProductos.objects.filter(conector=conector).count(), 1)

    @patch("oportunidades.services.conector_catalogo_service.requests.get")
    def test_conector_no_hace_scraping(self, requests_get):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente_verde,
            nombre="Manual",
            tipo_conector=ConectorFuente.TIPO_CSV_MANUAL,
            estado=ConectorFuente.ESTADO_ACTIVO,
            fuente_autorizo_uso=True,
        )
        ejecutar_conector_catalogo(conector)

        requests_get.assert_not_called()
