from decimal import Decimal

from django.core.management import call_command
from django.test import Client, TestCase

from oportunidades.models import (
    CandidatoCompra,
    CategoriaInteres,
    DuplicadoIgnorado,
    FuenteWeb,
    OperacionCuraduria,
    PoliticaExtraccionFuente,
    PrecioFuente,
    ProductoCanonico,
    ProductoFuente,
    ResultadoExtraccionWeb,
    ConectorFuente,
    ConfiguracionExtractorWeb,
    EjecucionConector,
)
from oportunidades.services.curaduria_service import fusionar_producto_fuente, generar_grupos_duplicados
from oportunidades.services.ranking_comercial_service import calcular_score_comercial_producto_fuente


class Etapa313Tests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")
        self.categoria = CategoriaInteres.objects.create(nombre="Cocina", palabra_clave="cocina")
        self.fuente = FuenteWeb.objects.create(nombre="Ganga Home", url_base="https://ganga.example/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE)
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
            url_producto="https://ganga.example/producto/rallador",
            imagen_url="https://ganga.example/rallador.jpg",
            condicion="nuevo",
        )
        PrecioFuente.objects.create(
            producto_fuente=self.producto,
            precio=Decimal("21000.00"),
            precio_lista=Decimal("30000.00"),
            precio_transferencia=Decimal("21000.00"),
            precio_tarjeta=Decimal("25000.00"),
            precio_oportunidad=Decimal("21000.00"),
            tipo_precio_oportunidad=PrecioFuente.TIPO_PRECIO_TRANSFERENCIA,
            origen_dato=PrecioFuente.ORIGEN_SCRAPING,
        )
        PrecioFuente.objects.create(
            producto_fuente=self.producto,
            precio=Decimal("24000.00"),
            precio_lista=Decimal("30000.00"),
            precio_transferencia=Decimal("24000.00"),
            precio_oportunidad=Decimal("24000.00"),
            tipo_precio_oportunidad=PrecioFuente.TIPO_PRECIO_TRANSFERENCIA,
            origen_dato=PrecioFuente.ORIGEN_SCRAPING,
        )

    def test_dashboard_curaduria_carga(self):
        self.assertEqual(self.client.get("/curaduria/dashboard/").status_code, 200)

    def test_lista_curaduria_productos_carga(self):
        self.assertEqual(self.client.get("/curaduria/productos/").status_code, 200)

    def test_detalle_curaduria_producto_carga(self):
        self.assertEqual(self.client.get(f"/curaduria/productos/{self.producto.pk}/").status_code, 200)

    def test_editar_producto_fuente_curaduria(self):
        response = self.client.post(
            f"/curaduria/productos/{self.producto.pk}/editar/",
            {
                "titulo_original": "Rallador Bambu Curado",
                "producto_canonico": self.canonico.pk,
                "url_producto": self.producto.url_producto,
                "imagen_url": self.producto.imagen_url,
                "condicion": "nuevo",
                "disponible": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.titulo_original, "Rallador Bambu Curado")

    def test_editar_precio_reciente(self):
        response = self.client.post(
            f"/curaduria/productos/{self.producto.pk}/editar-precio/",
            {
                "precio_lista": "32000.00",
                "precio_transferencia": "22000.00",
                "precio_tarjeta": "25000.00",
                "precio_oportunidad": "22000.00",
                "tipo_precio_oportunidad": PrecioFuente.TIPO_PRECIO_TRANSFERENCIA,
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_detectar_duplicados_por_url(self):
        ProductoFuente.objects.create(
            producto_canonico=self.canonico,
            fuente_web=self.fuente,
            titulo_original="Rallador Bambu",
            url_producto=self.producto.url_producto,
            condicion="nuevo",
        )
        self.assertTrue(generar_grupos_duplicados())

    def test_fusionar_producto_fuente_no_borra_historial(self):
        otro = ProductoFuente.objects.create(
            producto_canonico=self.canonico,
            fuente_web=self.fuente,
            titulo_original="Rallador Bambu Duplicado",
            url_producto="https://ganga.example/producto/rallador-2",
            condicion="nuevo",
        )
        PrecioFuente.objects.create(producto_fuente=otro, precio=1, origen_dato=PrecioFuente.ORIGEN_MANUAL)
        fusionar_producto_fuente(otro.pk, self.producto.pk)
        self.assertEqual(PrecioFuente.objects.filter(producto_fuente=self.producto).count(), 3)
        otro.refresh_from_db()
        self.assertTrue(otro.descartado_curaduria)

    def test_fusionar_producto_fuente_registra_operacion(self):
        otro = ProductoFuente.objects.create(
            producto_canonico=self.canonico,
            fuente_web=self.fuente,
            titulo_original="Rallador Bambu Duplicado",
            url_producto="https://ganga.example/producto/rallador-3",
            condicion="nuevo",
        )
        fusionar_producto_fuente(otro.pk, self.producto.pk)
        self.assertTrue(OperacionCuraduria.objects.filter(tipo_operacion=OperacionCuraduria.TIPO_FUSIONAR).exists())

    def test_ignorar_duplicado(self):
        otro = ProductoFuente.objects.create(
            producto_canonico=self.canonico,
            fuente_web=self.fuente,
            titulo_original="Rallador Bambu Duplicado",
            url_producto="https://ganga.example/producto/rallador-4",
            condicion="nuevo",
        )
        response = self.client.post(f"/curaduria/duplicados/{self.producto.pk}/{otro.pk}/ignorar/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DuplicadoIgnorado.objects.exists())

    def test_actualizar_producto_desde_preview_no_duplica(self):
        conector = ConectorFuente.objects.create(
            fuente_web=self.fuente,
            nombre="Extractor",
            tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            estado=ConectorFuente.ESTADO_ACTIVO,
        )
        ConfiguracionExtractorWeb.objects.create(conector=conector, url_inicio="https://ganga.example", dominio_permitido="ganga.example")
        ejecucion = EjecucionConector.objects.create(conector=conector)
        resultado = ResultadoExtraccionWeb.objects.create(
            ejecucion=ejecucion,
            producto_fuente=self.producto,
            titulo="Rallador actualizado",
            precio_decimal=Decimal("20000.00"),
            precio_oportunidad_decimal=Decimal("20000.00"),
            estado=ResultadoExtraccionWeb.ESTADO_PROCESADO,
        )
        response = self.client.post(f"/curaduria/previews/{resultado.pk}/actualizar-producto/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductoFuente.objects.count(), 1)

    def test_desvincular_preview_no_borra_producto(self):
        conector = ConectorFuente.objects.create(fuente_web=self.fuente, nombre="Extractor", tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO)
        ejecucion = EjecucionConector.objects.create(conector=conector)
        resultado = ResultadoExtraccionWeb.objects.create(ejecucion=ejecucion, producto_fuente=self.producto, titulo="Preview")
        response = self.client.post(f"/curaduria/previews/{resultado.pk}/desvincular/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductoFuente.objects.count(), 1)

    def test_score_comercial_alto_con_transferencia_descuento_historial(self):
        resultado = calcular_score_comercial_producto_fuente(self.producto)
        self.assertGreaterEqual(resultado["score"], 70)
        self.assertIn(resultado["nivel"], {"alto", "medio"})

    def test_score_comercial_penaliza_url_tecnica(self):
        self.producto.url_tecnica_generada = True
        self.producto.requiere_revision = True
        self.producto.save()
        resultado = calcular_score_comercial_producto_fuente(self.producto)
        self.assertEqual(resultado["nivel"], "revisar")

    def test_recalcular_ranking_comercial_command(self):
        call_command("recalcular_ranking_comercial")
        self.producto.refresh_from_db()
        self.assertGreaterEqual(self.producto.score_comercial, 1)

    def test_ranking_view_carga(self):
        self.assertEqual(self.client.get("/oportunidades/ranking/").status_code, 200)

    def test_marcar_candidato_compra(self):
        response = self.client.post(f"/oportunidades/ranking/{self.producto.pk}/candidato/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CandidatoCompra.objects.exists())

    def test_lista_candidatos_compra_carga(self):
        CandidatoCompra.objects.create(producto_fuente=self.producto)
        self.assertEqual(self.client.get("/oportunidades/candidatos-compra/").status_code, 200)

    def test_manual_operativo_existe(self):
        from pathlib import Path

        self.assertTrue(
            Path("/app/docs/manual_operativo_radar.md").exists()
            or Path("/app/../docs/manual_operativo_radar.md").exists()
            or Path("docs/manual_operativo_radar.md").exists()
        )
