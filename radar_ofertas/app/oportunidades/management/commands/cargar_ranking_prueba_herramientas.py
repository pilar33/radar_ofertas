from datetime import date

from django.core.management.base import BaseCommand

from oportunidades.models import CategoriaInteres, LoteRanking
from oportunidades.services.ranking_import_service import confirmar_importacion_ranking, previsualizar_ranking


TABLA = """| Ranking | Producto | Categoria | Tienda donde aparece fuerte | Senal de venta | URL |
|---:|---|---|---|---|---|
| 1 | Taladro atornillador percutor Lusqtoff 18V + 2 baterias + puntas | Herramientas electricas | Mercado Libre | Figura como 1 mas vendido en herramientas electricas. | https://www.mercadolibre.com.ar/mas-vendidos/MLA5228 |
| 2 | Set herramientas Black+Decker 124/125 piezas | Kit de herramientas | Mercado Libre | Aparece como producto destacado o mas vendido en busquedas de kits. | https://listado.mercadolibre.com.ar/kit-herramientas |
| 3 | Maletin completo de 245 herramientas Lusqtoff / PideWeb | Kit general | Mercado Libre | Mercado Libre lo marca como MAS VENDIDO en herramientas. | https://listado.mercadolibre.com.ar/herramientas |
| 4 | Amoladora Angular Black & Decker G720N-AR | Herramienta electrica | Fravega | Primer producto del bloque Fijate lo mas vendidos. | https://www.fravega.com/e/catalogo-herramientas/ |
| 5 | Motosierra 52cc espada 50 cm / 20 pulgadas | Jardin / obra | Fravega | Aparece segunda en la seccion de mas vendidos. | https://www.fravega.com/e/catalogo-herramientas/ |
| 6 | Bomba presurizadora 120W Vasser / Motorarg | Construccion / plomeria | Fravega | Aparece tercera en la seccion de mas vendidos. | https://www.fravega.com/e/catalogo-herramientas/ |
| 7 | Amoladora Bosch GWS 700 Professional 115 mm | Herramienta electrica | Fravega | Esta entre los primeros productos del bloque de mas vendidos. | https://www.fravega.com/e/catalogo-herramientas/ |
| 8 | Combo Amoladora Angular + Taladro Percutor Daewoo 750W | Combo herramientas | Fravega | Aparece dentro del bloque de mas vendidos. | https://www.fravega.com/e/catalogo-herramientas/ |
| 9 | Hidrolavadora Philco Pro 1400W 110 bar | Hogar / limpieza / obra | Fravega | Figura dentro de los mas vendidos de herramientas y hogar. | https://www.fravega.com/e/catalogo-herramientas/ |
| 10 | Lijadora Orbital Black & Decker BS200-AR | Carpinteria / terminaciones | Fravega | Esta en la seccion de mas vendidos. | https://www.fravega.com/e/catalogo-herramientas/ |
"""


class Command(BaseCommand):
    help = "Carga el lote de prueba de herramientas con senales de alta venta como borrador."

    def add_arguments(self, parser):
        parser.add_argument("--fecha", default=None, help="Fecha de referencia YYYY-MM-DD. Default: hoy.")
        parser.add_argument("--permitir-duplicado", action="store_true")

    def handle(self, *args, **options):
        fecha = date.fromisoformat(options["fecha"]) if options["fecha"] else date.today()
        categoria = CategoriaInteres.objects.filter(slug="herramientas").first()
        preview = previsualizar_ranking(TABLA, fecha_referencia=fecha, alcance="herramientas")
        datos_lote = {
            "nombre": "Herramientas con senales de alta venta",
            "tipo_ranking": LoteRanking.TIPO_ALTA_VENTA,
            "alcance": "herramientas",
            "categoria_id": categoria.id if categoria else None,
            "fecha_referencia": fecha,
            "origen": "Radar ChatGPT - carga manual",
            "metodologia": "Tabla inicial de prueba cargada desde comando.",
            "estado": LoteRanking.ESTADO_BORRADOR,
            "hash_importacion": preview["hash"],
        }
        lote = confirmar_importacion_ranking(
            datos_lote,
            preview["filas"],
            TABLA,
            permitir_duplicado=options["permitir_duplicado"],
        )
        self.stdout.write(self.style.SUCCESS(f"Lote de prueba creado como borrador. ID: {lote.id}. Filas: {lote.cantidad_filas}."))
