from dataclasses import dataclass

from oportunidades.models import ConectorFuente
from oportunidades.services.auditoria_fuentes_service import hacer_request_controlado
from oportunidades.services.conectores_service import validar_conector_segun_politica


@dataclass
class ResultadoRevisionWeb:
    ok: bool
    mensaje: str
    datos: dict | None = None


class ConectorWebBase:
    def __init__(self, conector):
        self.conector = conector

    def validar_politica(self):
        return validar_conector_segun_politica(self.conector)

    def puede_ejecutar(self):
        validacion = self.validar_politica()
        return validacion["valido"] and validacion["nivel"] == "ok"

    def obtener_headers(self):
        return {
            "User-Agent": "radar_ofertas/1.0",
            "Accept-Language": "es-AR,es;q=0.9",
        }

    def request_controlado(self, url):
        return hacer_request_controlado(url)

    def extraer_productos_preview(self):
        if self.conector.tipo_conector != ConectorFuente.TIPO_SCRAPING_PERMITIDO:
            return ResultadoRevisionWeb(False, "El conector no es de tipo scraping_permitido.")
        return ResultadoRevisionWeb(
            False,
            "No implementado. Requiere semaforo verde/amarillo y revision manual.",
        )
