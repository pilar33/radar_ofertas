from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from oportunidades.models import LoteCapturaLocal
from oportunidades.services.oportunidades_locales_service import confirmar_importacion_local, previsualizar_importacion_local


TABLA_EJEMPLO = """| Ranking | Producto | Fuente | Zona | Precio encontrado | Presentacion | Unidad normalizada | Sirve para | Estado |
|---:|---|---|---|---:|---|---|---|---|
| 1 | Menudo de pollo | Vea fisico | Salta Capital | 300 | 1 kg | $/kg | alimentacion economica / alimentacion animal informada | ALERTA FUERTE |
| 2 | Fideos segunda marca | Mayorista calle Oran | calle Oran, Salta Capital | 500 | paquete de 500 g | $/kg | compra economica / stock / alimentacion animal informada | ALERTA FUERTE |
| 3 | Arroz economico | Mayorista local | Salta Capital | precio a cargar | bolsa de 1 kg | $/kg | consumo familiar / stock | VIGILAR |
| 4 | Azucar por fardo | Mayorista local | Salta Capital | precio a cargar | fardo | $/kg y $/bolsa | consumo / posible reventa | VIGILAR |
| 5 | Papel higienico pack grande | Supermercado o mayorista | Salta Capital | precio a cargar | pack | $/metro | consumo / stock | VIGILAR |
| 6 | Aceite por caja | Mayorista o supermercado | Salta Capital | precio a cargar | caja | $/litro | consumo / posible reventa | VIGILAR |
| 7 | Polenta, harina o arroz partido | Mayorista local | Salta Capital | precio a cargar | bolsa o paquete | $/kg | stock / alimentacion economica | VIGILAR |
"""


class Command(BaseCommand):
    help = "Carga el lote de ejemplo de oportunidades locales como borrador."

    def handle(self, *args, **options):
        call_command("inicializar_oportunidades_locales")
        fecha = timezone.now()
        preview = previsualizar_importacion_local(
            TABLA_EJEMPLO,
            fecha_observacion=fecha,
            zona="Salta Capital",
            metodo=LoteCapturaLocal.METODO_TABLA_MARKDOWN,
            formato="markdown",
        )
        lote = confirmar_importacion_local(
            {
                "nombre": "Lote ejemplo oportunidades locales Salta",
                "fecha_observacion": fecha,
                "zona": "Salta Capital",
                "metodo_captura": LoteCapturaLocal.METODO_TABLA_MARKDOWN,
                "estado": LoteCapturaLocal.ESTADO_BORRADOR,
                "hash_importacion": preview["hash"],
                "permitir_duplicado": True,
            },
            preview["filas"],
            TABLA_EJEMPLO,
            permitir_duplicado=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Lote local ejemplo creado: {lote.id}. Observaciones: {lote.observaciones_precio.count()}. Objetivos: {lote.objetivos.count()}.")) 
