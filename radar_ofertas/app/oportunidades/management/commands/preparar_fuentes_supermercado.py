from django.core.management.base import BaseCommand

from oportunidades.models import FuenteWeb, PoliticaExtraccionFuente


FUENTES = [
    ("Carrefour Argentina", "https://www.carrefour.com.ar/", "supermercado/minorista"),
    ("Carrefour Maxi Pedido", "https://www.carrefour.com.ar/", "mayorista/comerciante"),
    ("Vea Digital", "https://www.veadigital.com.ar/", "supermercado"),
    ("Chango Mas / MasOnline", "https://www.masonline.com.ar/", "supermercado"),
    ("Makro Argentina", "https://www.makro.com.ar/", "mayorista"),
    ("Vital", "https://www.vital.com.ar/", "mayorista"),
    ("Maxiconsumo", "https://www.maxiconsumo.com/", "mayorista"),
    ("Diarco", "https://www.diarco.com.ar/", "mayorista"),
]


class Command(BaseCommand):
    help = "Prepara fuentes candidatas de supermercado y mayoristas sin activar extraccion."

    def handle(self, *args, **options):
        creadas = actualizadas = 0
        for nombre, url, rubro in FUENTES:
            fuente, creada = FuenteWeb.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "url_base": url,
                    "tipo_fuente": FuenteWeb.TIPO_MAYORISTA if "mayorista" in rubro else FuenteWeb.TIPO_TIENDA_ONLINE,
                    "rubro_principal": rubro,
                    "descripcion": (
                        "Fuente candidata para supermercado/mayorista. Pendiente revisar cobertura en Argentina, "
                        "Salta Capital, sucursal, entrega/retiro, vigencia y limitaciones por cliente."
                    ),
                    "activa": True,
                    "prioridad": 50,
                    "pais": "Argentina",
                },
            )
            if not creada:
                fuente.rubro_principal = fuente.rubro_principal or rubro
                fuente.descripcion = fuente.descripcion or "Fuente candidata pendiente de revision manual."
                fuente.save(update_fields=["rubro_principal", "descripcion", "fecha_actualizacion"])
                actualizadas += 1
            else:
                creadas += 1
            PoliticaExtraccionFuente.objects.get_or_create(
                fuente=fuente,
                defaults={
                    "semaforo": PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
                    "metodo_preferido": PoliticaExtraccionFuente.METODO_PENDIENTE_REVISION,
                    "permite_scraping": False,
                    "robots_txt_revisado": False,
                    "terminos_revisados": False,
                    "requiere_login": False,
                    "tiene_captcha": False,
                    "observaciones": "No habilitar extraccion hasta completar revision manual de politicas y cobertura Salta Capital.",
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Fuentes candidatas listas. Creadas: {creadas}. Actualizadas: {actualizadas}."))
