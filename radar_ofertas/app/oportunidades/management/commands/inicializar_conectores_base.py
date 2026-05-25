from django.core.management.base import BaseCommand

from oportunidades.models import ConectorFuente, FuenteWeb, PoliticaExtraccionFuente


class Command(BaseCommand):
    help = "Crea conectores base segun fuentes y politicas existentes."

    def handle(self, *args, **options):
        creados = 0
        actualizados = 0

        for fuente in FuenteWeb.objects.filter(activa=True).select_related("politica_extraccion"):
            politica = getattr(fuente, "politica_extraccion", None)
            metodo = politica.metodo_preferido if politica else None
            definiciones = []

            if fuente.nombre == "Mercado Libre":
                definiciones.append(
                    {
                        "nombre": "Mercado Libre API restringida",
                        "tipo_conector": ConectorFuente.TIPO_API_OFICIAL,
                        "estado": ConectorFuente.ESTADO_PAUSADO,
                        "descripcion": (
                            "OAuth funciona, pero endpoints de catalogo/busqueda/productos devuelven 403 por PolicyAgent."
                        ),
                    }
                )
            if fuente.tipo_fuente == FuenteWeb.TIPO_EXCEL_CSV or metodo == PoliticaExtraccionFuente.METODO_CSV_EXCEL:
                definiciones.append(
                    {
                        "nombre": "Importacion CSV/Excel manual",
                        "tipo_conector": ConectorFuente.TIPO_CSV_MANUAL,
                        "estado": ConectorFuente.ESTADO_ACTIVO,
                        "descripcion": "Importacion manual de listas de precios autorizadas.",
                    }
                )
            if fuente.tipo_fuente == FuenteWeb.TIPO_MANUAL_ASISTIDA or metodo == PoliticaExtraccionFuente.METODO_CARGA_URL:
                definiciones.append(
                    {
                        "nombre": "Carga asistida por URL",
                        "tipo_conector": ConectorFuente.TIPO_CARGA_URL,
                        "estado": ConectorFuente.ESTADO_ACTIVO,
                        "descripcion": "Carga manual de productos candidatos por URL, sin scraping.",
                    }
                )

            for definicion in definiciones:
                _, creado = ConectorFuente.objects.update_or_create(
                    fuente_web=fuente,
                    nombre=definicion["nombre"],
                    defaults={
                        **definicion,
                        "requiere_revision_manual": True,
                        "respeta_politica_fuente": True,
                    },
                )
                creados += int(creado)
                actualizados += int(not creado)

        self.stdout.write(self.style.SUCCESS("Conectores base inicializados."))
        self.stdout.write(f"Creados: {creados}")
        self.stdout.write(f"Actualizados: {actualizados}")
