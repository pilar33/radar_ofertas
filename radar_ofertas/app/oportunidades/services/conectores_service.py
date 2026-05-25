from django.utils import timezone

from oportunidades.models import (
    ConectorFuente,
    DetalleEjecucionConector,
    EjecucionConector,
    PoliticaExtraccionFuente,
)


TIPOS_MANUALES_PERMITIDOS = {
    ConectorFuente.TIPO_CSV_MANUAL,
    ConectorFuente.TIPO_EXCEL_MANUAL,
    ConectorFuente.TIPO_CARGA_URL,
}


def validar_conector_segun_politica(conector):
    politica = getattr(conector.fuente_web, "politica_extraccion", None)
    if not politica:
        return {
            "valido": False,
            "mensaje": "La fuente no tiene politica de extraccion definida.",
            "nivel": "advertencia",
        }

    if conector.tipo_conector == ConectorFuente.TIPO_SCRAPING_PERMITIDO:
        if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO:
            return {"valido": False, "mensaje": "Semaforo desconocido: scraping bloqueado.", "nivel": "bloqueado"}
        if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_ROJO:
            return {"valido": False, "mensaje": "Fuente roja: scraping bloqueado.", "nivel": "bloqueado"}
        if politica.requiere_login or politica.tiene_captcha:
            return {"valido": False, "mensaje": "Login o captcha detectado: scraping bloqueado.", "nivel": "bloqueado"}
        if not politica.permite_scraping:
            return {"valido": False, "mensaje": "La politica no permite scraping.", "nivel": "bloqueado"}
        if not politica.robots_txt_revisado:
            return {"valido": False, "mensaje": "Robots.txt no revisado: scraping bloqueado.", "nivel": "bloqueado"}
        if not politica.terminos_revisados:
            return {"valido": False, "mensaje": "Terminos no revisados: scraping bloqueado.", "nivel": "bloqueado"}
        if not conector.respeta_politica_fuente:
            return {"valido": False, "mensaje": "El conector no declara respetar la politica de fuente.", "nivel": "bloqueado"}
        if conector.requiere_revision_manual:
            return {
                "valido": True,
                "mensaje": "Scraping tecnicamente habilitable, pero requiere aprobacion manual antes de ejecutar.",
                "nivel": "advertencia",
            }
        return {"valido": True, "mensaje": "Scraping permitido por politica revisada.", "nivel": "ok"}

    if politica.metodo_preferido == PoliticaExtraccionFuente.METODO_NO_PERMITIDO:
        if conector.estado == ConectorFuente.ESTADO_ACTIVO:
            return {"valido": False, "mensaje": "Metodo no permitido: no activar conectores automaticos.", "nivel": "bloqueado"}
        return {"valido": True, "mensaje": "Conector no activo sobre fuente no permitida.", "nivel": "advertencia"}

    if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_ROJO:
        if conector.tipo_conector in {ConectorFuente.TIPO_CSV_MANUAL, ConectorFuente.TIPO_EXCEL_MANUAL} and (
            politica.metodo_preferido == PoliticaExtraccionFuente.METODO_CSV_EXCEL
        ):
            return {"valido": True, "mensaje": "CSV/Excel manual autorizado sobre fuente roja.", "nivel": "ok"}
        if conector.tipo_conector == ConectorFuente.TIPO_CARGA_URL:
            return {"valido": True, "mensaje": "Carga URL manual permitida; no automatiza extraccion.", "nivel": "ok"}
        return {"valido": False, "mensaje": "Fuente roja: conector automatico bloqueado.", "nivel": "bloqueado"}

    if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_AMARILLO:
        if conector.tipo_conector in TIPOS_MANUALES_PERMITIDOS:
            return {"valido": True, "mensaje": "Conector manual permitido en fuente amarilla.", "nivel": "ok"}
        return {
            "valido": True,
            "mensaje": "Fuente amarilla: requiere revision manual antes de automatizar.",
            "nivel": "advertencia",
        }

    if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_VERDE:
        if conector.tipo_conector in TIPOS_MANUALES_PERMITIDOS or conector.tipo_conector == ConectorFuente.TIPO_API_OFICIAL:
            return {"valido": True, "mensaje": "Conector compatible con fuente verde.", "nivel": "ok"}
        return {"valido": True, "mensaje": "Fuente verde, revisar detalles antes de ejecutar.", "nivel": "advertencia"}

    return {"valido": True, "mensaje": "Politica desconocida: requiere revision manual.", "nivel": "advertencia"}


def crear_ejecucion_conector(conector):
    return EjecucionConector.objects.create(conector=conector, estado=EjecucionConector.ESTADO_PENDIENTE)


def finalizar_ejecucion_conector(ejecucion, resumen):
    errores = int(resumen.get("errores", 0) or 0)
    ejecucion.estado = (
        EjecucionConector.ESTADO_FINALIZADA_CON_ERRORES if errores else EjecucionConector.ESTADO_FINALIZADA
    )
    ejecucion.fin = timezone.now()
    for campo in [
        "productos_detectados",
        "productos_creados",
        "productos_actualizados",
        "precios_creados",
        "errores",
        "mensaje",
        "log_resumido",
    ]:
        if campo in resumen:
            setattr(ejecucion, campo, resumen[campo])
    ejecucion.save()
    ejecucion.conector.ultima_ejecucion = ejecucion.fin
    ejecucion.conector.save(update_fields=["ultima_ejecucion", "fecha_actualizacion"])
    return ejecucion


def registrar_detalle_ejecucion(ejecucion, estado, mensaje, producto_fuente=None, datos_originales=None):
    return DetalleEjecucionConector.objects.create(
        ejecucion=ejecucion,
        estado=estado,
        mensaje=mensaje,
        producto_fuente=producto_fuente,
        datos_originales=datos_originales,
    )
