from django.core.management.base import BaseCommand

from oportunidades.models import DecisionTecnica, FuenteWeb, PoliticaExtraccionFuente
from oportunidades.services.documentacion_service import registrar_decision_tecnica
from oportunidades.services.fuentes_service import registrar_fuente_web


class Command(BaseCommand):
    help = "Inicializa fuentes, politicas y decisiones tecnicas de la arquitectura multifuente."

    def handle(self, *args, **options):
        mercado_libre = registrar_fuente_web(
            nombre="Mercado Libre",
            url_base="https://www.mercadolibre.com.ar",
            tipo_fuente=FuenteWeb.TIPO_MARKETPLACE,
            rubro_principal="general",
            descripcion="Marketplace general. OAuth funciona, pero endpoints de catalogo/busqueda/productos estan restringidos.",
            prioridad=1,
            politica={
                "semaforo": PoliticaExtraccionFuente.SEMAFORO_ROJO,
                "metodo_preferido": PoliticaExtraccionFuente.METODO_CARGA_URL,
                "tiene_api": True,
                "tiene_afiliados": True,
                "permite_scraping": False,
                "riesgo_tecnico": PoliticaExtraccionFuente.RIESGO_ALTO,
                "riesgo_legal": PoliticaExtraccionFuente.RIESGO_MEDIO,
                "observaciones": (
                    "OAuth funciona pero endpoints de catalogo/busqueda/productos devuelven 403 por "
                    "PA_UNAUTHORIZED_RESULT_FROM_POLICIES. No usar como fuente automatica principal por ahora."
                ),
            },
        )

        registrar_fuente_web(
            nombre="Deco Home",
            url_base="https://example.com/deco-home",
            tipo_fuente=FuenteWeb.TIPO_TIENDA_ONLINE,
            rubro_principal="deco/hogar/bazar",
            descripcion="Fuente candidata para revision.",
            prioridad=2,
            politica={
                "semaforo": PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
                "metodo_preferido": PoliticaExtraccionFuente.METODO_PENDIENTE_REVISION,
                "riesgo_tecnico": PoliticaExtraccionFuente.RIESGO_DESCONOCIDO,
                "riesgo_legal": PoliticaExtraccionFuente.RIESGO_DESCONOCIDO,
                "observaciones": "Fuente candidata para revision. Antes de automatizar se debe revisar robots.txt, terminos y estructura.",
            },
        )

        registrar_fuente_web(
            nombre="Mayoristas / catalogos",
            url_base="https://example.com/mayoristas-catalogos",
            tipo_fuente=FuenteWeb.TIPO_EXCEL_CSV,
            rubro_principal="varios",
            descripcion="Fuente conceptual para listas de precios y catalogos de proveedores.",
            prioridad=3,
            politica={
                "semaforo": PoliticaExtraccionFuente.SEMAFORO_VERDE,
                "metodo_preferido": PoliticaExtraccionFuente.METODO_CSV_EXCEL,
                "riesgo_tecnico": PoliticaExtraccionFuente.RIESGO_BAJO,
                "riesgo_legal": PoliticaExtraccionFuente.RIESGO_BAJO,
                "observaciones": "Fuente recomendable cuando el proveedor entrega lista de precios o catalogo.",
            },
        )

        registrar_fuente_web(
            nombre="Carga asistida",
            url_base="https://radar-ofertas.local/carga-asistida",
            tipo_fuente=FuenteWeb.TIPO_MANUAL_ASISTIDA,
            rubro_principal="general",
            descripcion="Carga manual o por URL asistida para candidatos.",
            prioridad=4,
            politica={
                "semaforo": PoliticaExtraccionFuente.SEMAFORO_VERDE,
                "metodo_preferido": PoliticaExtraccionFuente.METODO_CARGA_URL,
                "riesgo_tecnico": PoliticaExtraccionFuente.RIESGO_BAJO,
                "riesgo_legal": PoliticaExtraccionFuente.RIESGO_BAJO,
                "observaciones": "Se usa para cargar productos candidatos cuando no hay API o automatizacion permitida.",
            },
        )

        registrar_decision_tecnica(
            titulo="Mercado Libre no sera fuente automatica principal en esta etapa",
            categoria=DecisionTecnica.CATEGORIA_MERCADO_LIBRE,
            descripcion=(
                "OAuth funciona y /users/me responde 200, pero los endpoints /sites/MLA/search, "
                "/sites/MLA/categories e /items/{id} devuelven 403 por PolicyAgent."
            ),
            decision="Mantener Mercado Libre como fuente limitada/opcional y avanzar con arquitectura multifuente.",
            motivo="Evitar depender de una API bloqueada por politicas externas.",
            impacto=(
                "Se prioriza base propia de fuentes, conectores permitidos, CSV/Excel, carga por URL "
                "y futuras integraciones alternativas."
            ),
        )

        self.stdout.write(self.style.SUCCESS("Base multifuente inicializada."))
        self.stdout.write(f"Fuente documentada: {mercado_libre.nombre}")
