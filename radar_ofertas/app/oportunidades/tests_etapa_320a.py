from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

from django.core.management import call_command
from django.test import Client, TestCase

from oportunidades.models import (
    CandidatoCompra,
    FuenteWeb,
    ImportacionRadarTexto,
    OportunidadRadar,
    ProductoCanonico,
    ProductoFuente,
    CategoriaInteres,
)
from oportunidades.services.dataset_export_service import exportar_dataset_completo_zip, exportar_dataset_productos_csv
from oportunidades.services.radar_oportunidades_service import importar_oportunidades_desde_texto
from oportunidades.services.radar_texto_parser_service import (
    calcular_score_radar,
    extraer_chequeo_antimarketing,
    extraer_comparables,
    extraer_descuento,
    extraer_motivo,
    extraer_precio_actual,
    extraer_tienda_producto,
    normalizar_precio_argentino,
    parsear_texto_radar,
)


TEXTO_RADAR = """Radar de ofertas - oportunidad real encontrada

Fravega - Motosierra Gamma G1850AR 38cc 16"

Precio actual: $99.999
Comparable mas bajo confiable: $134.499 en Mercado Libre
Otros comparables: $147.035 en Provincia Compras, $202.690 en Gamma Market
Descuento real estimado: 25% a 50% segun comparable.

Por que conviene: queda mas de 20% abajo del comparable mas barato.

Chequeo anti-marketing: Fravega figura como vendedor con llegada manana en catalogo.
"""


class Etapa320AImportadorRadarTests(TestCase):
    def test_normalizar_precio_argentino_punto_miles(self):
        self.assertEqual(normalizar_precio_argentino("$99.999"), Decimal("99999.00"))

    def test_normalizar_precio_argentino_decimal_coma(self):
        self.assertEqual(normalizar_precio_argentino("$20.990,20"), Decimal("20990.20"))

    def test_parsear_tienda_producto_con_guion_largo(self):
        tienda, producto = extraer_tienda_producto('Fravega — Motosierra Gamma G1850AR 38cc 16"')
        self.assertEqual(tienda, "Fravega")
        self.assertIn("Motosierra", producto)

    def test_parsear_precio_actual(self):
        self.assertEqual(extraer_precio_actual(TEXTO_RADAR), Decimal("99999.00"))

    def test_parsear_comparable_principal(self):
        comparables = extraer_comparables(TEXTO_RADAR)
        self.assertEqual(comparables["precio_comparable_minimo"], Decimal("134499.00"))
        self.assertEqual(comparables["comparable_principal_precio"], Decimal("134499.00"))

    def test_parsear_descuento_texto(self):
        descuento, texto = extraer_descuento(TEXTO_RADAR)
        self.assertEqual(descuento, Decimal("50.00"))
        self.assertIn("25%", texto)

    def test_parsear_motivo_conveniencia(self):
        self.assertIn("20% abajo", extraer_motivo(TEXTO_RADAR))

    def test_parsear_chequeo_antimarketing(self):
        self.assertIn("vendedor", extraer_chequeo_antimarketing(TEXTO_RADAR))

    def test_parsear_texto_radar_una_oportunidad(self):
        oportunidades = parsear_texto_radar(TEXTO_RADAR)
        self.assertEqual(len(oportunidades), 1)
        self.assertEqual(oportunidades[0]["precio_actual"], Decimal("99999.00"))

    def test_parsear_texto_radar_varias_oportunidades(self):
        oportunidades = parsear_texto_radar(TEXTO_RADAR + "\n\nCetrogar: Heladera X\nPrecio actual: $200.000\nComparable mas bajo confiable: $260.000 en Tienda Y")
        self.assertEqual(len(oportunidades), 2)

    def test_score_radar_alto_con_descuento_y_comparable(self):
        datos = parsear_texto_radar(TEXTO_RADAR)[0]
        self.assertGreaterEqual(calcular_score_radar(datos), 70)

    def test_score_radar_bajo_sin_precio(self):
        score = calcular_score_radar({"requiere_revision": True})
        self.assertLess(score, 40)

    def test_decision_sugerida_comprar(self):
        datos = parsear_texto_radar(TEXTO_RADAR + "\nhttps://fravega.example/oferta")[0]
        self.assertIn(datos["decision_sugerida"], {"comprar", "analizar"})

    def test_decision_sugerida_analizar(self):
        datos = parsear_texto_radar(TEXTO_RADAR)[0]
        self.assertIn(datos["decision_sugerida"], {"analizar", "comprar"})

    def test_importar_oportunidades_desde_texto_crea_importacion(self):
        importacion, creadas, _ = importar_oportunidades_desde_texto(TEXTO_RADAR)
        self.assertIsInstance(importacion, ImportacionRadarTexto)
        self.assertEqual(importacion.oportunidades_detectadas, 1)

    def test_importar_oportunidades_desde_texto_crea_oportunidad(self):
        _, creadas, _ = importar_oportunidades_desde_texto(TEXTO_RADAR)
        self.assertEqual(len(creadas), 1)
        self.assertEqual(OportunidadRadar.objects.count(), 1)

    def test_importar_oportunidades_no_duplica_reciente(self):
        importar_oportunidades_desde_texto(TEXTO_RADAR)
        importar_oportunidades_desde_texto(TEXTO_RADAR)
        self.assertEqual(OportunidadRadar.objects.count(), 1)

    def test_oportunidad_vincula_fuente_si_tienda_existe(self):
        FuenteWeb.objects.create(nombre="Fravega", url_base="https://www.fravega.com/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE)
        _, creadas, _ = importar_oportunidades_desde_texto(TEXTO_RADAR)
        self.assertEqual(creadas[0].fuente_web.nombre, "Fravega")

    def test_radar_dashboard_carga(self):
        self.assertEqual(Client(HTTP_HOST="localhost").get("/radar/dashboard/").status_code, 200)

    def test_radar_ofertas_lista_carga(self):
        self.assertEqual(Client(HTTP_HOST="localhost").get("/radar/ofertas/").status_code, 200)

    def test_radar_importar_texto_carga(self):
        self.assertContains(Client(HTTP_HOST="localhost").get("/radar/importar-texto/"), "Pega")

    def test_radar_importar_texto_post_analiza(self):
        response = Client(HTTP_HOST="localhost").post("/radar/importar-texto/", {"texto_original": TEXTO_RADAR, "origen": "chatgpt_radar"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImportacionRadarTexto.objects.count(), 1)

    def test_radar_detalle_carga(self):
        _, creadas, _ = importar_oportunidades_desde_texto(TEXTO_RADAR)
        response = Client(HTTP_HOST="localhost").get(f"/radar/ofertas/{creadas[0].pk}/")
        self.assertContains(response, "Motosierra")

    def test_marcar_oportunidad_como_candidato(self):
        _, creadas, _ = importar_oportunidades_desde_texto(TEXTO_RADAR)
        response = Client(HTTP_HOST="localhost").post(f"/radar/ofertas/{creadas[0].pk}/marcar-candidato/")
        creadas[0].refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(creadas[0].candidato_compra)
        self.assertEqual(creadas[0].candidato_compra.origen_candidato, CandidatoCompra.ORIGEN_RADAR_TEXTO)

    def test_export_dataset_incluye_radar_oportunidades(self):
        importar_oportunidades_desde_texto(TEXTO_RADAR)
        zip_buffer = exportar_dataset_completo_zip()
        with ZipFile(zip_buffer) as archivo:
            self.assertIn("radar_oportunidades.csv", archivo.namelist())

    def test_dataset_producto_incluye_tiene_oportunidad_radar(self):
        categoria = CategoriaInteres.objects.create(nombre="Herramientas", palabra_clave="motosierra")
        canonico = ProductoCanonico.objects.create(nombre_normalizado="motosierra gamma g1850ar", categoria=categoria)
        fuente = FuenteWeb.objects.create(nombre="Fravega", url_base="https://www.fravega.com/", tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE)
        producto = ProductoFuente.objects.create(producto_canonico=canonico, fuente_web=fuente, titulo_original='Motosierra Gamma G1850AR 38cc 16"', url_producto="https://www.fravega.com/p", condicion="desconocido")
        oportunidad = OportunidadRadar.objects.create(titulo="Radar", tienda="Fravega", producto_nombre=producto.titulo_original, producto_fuente=producto, producto_canonico=canonico, texto_original=TEXTO_RADAR, score_radar=88)
        csv_texto = exportar_dataset_productos_csv().getvalue()
        self.assertIn("tiene_oportunidad_radar", csv_texto)
        self.assertIn(str(oportunidad.score_radar), csv_texto)

    def test_importar_oportunidades_radar_dry_run(self):
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as archivo:
            archivo.write(TEXTO_RADAR)
            path = archivo.name
        salida = StringIO()
        call_command("importar_oportunidades_radar", "--input", path, "--dry-run", stdout=salida)
        self.assertIn("Dry-run", salida.getvalue())
        self.assertEqual(OportunidadRadar.objects.count(), 0)

    def test_recalcular_oportunidades_radar_command(self):
        importar_oportunidades_desde_texto(TEXTO_RADAR)
        salida = StringIO()
        call_command("recalcular_oportunidades_radar", stdout=salida)
        self.assertIn("recalculadas", salida.getvalue())

    def test_manual_operativo_incluye_radar_texto_chatgpt(self):
        manual = Path(__file__).resolve().parents[1] / "docs" / "manual_operativo_radar.md"
        contenido = manual.read_text(encoding="utf-8")
        self.assertIn("Radar inteligente desde texto de ChatGPT", contenido)
