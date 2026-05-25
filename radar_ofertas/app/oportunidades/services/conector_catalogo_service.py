from pathlib import PurePosixPath

import requests
from django.core.files.base import ContentFile

from oportunidades.models import ConectorFuente, EjecucionConector, ImportacionProductos, PoliticaExtraccionFuente
from oportunidades.services.conectores_service import (
    crear_ejecucion_conector,
    finalizar_ejecucion_conector,
    registrar_detalle_ejecucion,
    validar_conector_segun_politica,
)
from oportunidades.services.importacion_service import detectar_tipo_archivo, procesar_importacion


TIPOS_CATALOGO = {
    ConectorFuente.TIPO_CSV_MANUAL,
    ConectorFuente.TIPO_EXCEL_MANUAL,
    ConectorFuente.TIPO_CSV_REMOTO,
    ConectorFuente.TIPO_EXCEL_REMOTO,
}
TIPOS_REMOTOS = {ConectorFuente.TIPO_CSV_REMOTO, ConectorFuente.TIPO_EXCEL_REMOTO}
EXTENSIONES = {
    ".csv": ImportacionProductos.TIPO_CSV,
    ".xlsx": ImportacionProductos.TIPO_XLSX,
    ".xls": ImportacionProductos.TIPO_XLS,
}
CONTENT_TYPES_PERMITIDOS = (
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
)
MAX_BYTES = 10 * 1024 * 1024


def _extension_url(url):
    path = PurePosixPath((url or "").split("?", 1)[0])
    return path.suffix.lower()


def _formato_definido(conector):
    if conector.formato_recurso in {
        ConectorFuente.FORMATO_CSV,
        ConectorFuente.FORMATO_XLSX,
        ConectorFuente.FORMATO_XLS,
    }:
        return conector.formato_recurso
    return EXTENSIONES.get(_extension_url(conector.url_recurso), ConectorFuente.FORMATO_DESCONOCIDO)


def validar_conector_catalogo(conector):
    if conector.tipo_conector == ConectorFuente.TIPO_SCRAPING_PERMITIDO:
        return {"valido": False, "mensaje": "Este conector catalogo no ejecuta scraping.", "nivel": "bloqueado"}
    if conector.tipo_conector not in TIPOS_CATALOGO:
        return {"valido": False, "mensaje": "El conector no es CSV/Excel.", "nivel": "bloqueado"}
    if not conector.fuente_web.activa:
        return {"valido": False, "mensaje": "La fuente no esta activa.", "nivel": "bloqueado"}

    politica = getattr(conector.fuente_web, "politica_extraccion", None)
    if not politica:
        return {"valido": False, "mensaje": "La fuente no tiene politica de extraccion.", "nivel": "advertencia"}

    if conector.requiere_descarga and conector.tipo_conector not in TIPOS_REMOTOS:
        return {"valido": False, "mensaje": "Solo csv_remoto/excel_remoto pueden requerir descarga.", "nivel": "bloqueado"}
    if conector.url_recurso and conector.tipo_conector == ConectorFuente.TIPO_SCRAPING_PERMITIDO:
        return {"valido": False, "mensaje": "No se permite URL en conectores scraping en esta etapa.", "nivel": "bloqueado"}

    if conector.tipo_conector in TIPOS_REMOTOS:
        if not conector.url_recurso:
            return {"valido": False, "mensaje": "El conector remoto requiere URL directa al archivo.", "nivel": "bloqueado"}
        formato = _formato_definido(conector)
        if formato == ConectorFuente.FORMATO_DESCONOCIDO:
            return {"valido": False, "mensaje": "La URL debe ser CSV/XLSX/XLS o declarar formato.", "nivel": "bloqueado"}
        if _extension_url(conector.url_recurso) in {".html", ".htm"}:
            return {"valido": False, "mensaje": "No se aceptan archivos HTML como catalogo.", "nivel": "bloqueado"}

    if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_ROJO and conector.tipo_conector in TIPOS_REMOTOS:
        if politica.metodo_preferido != PoliticaExtraccionFuente.METODO_CSV_EXCEL or not conector.fuente_autorizo_uso:
            return {"valido": False, "mensaje": "Fuente roja: descarga remota bloqueada sin autorizacion CSV/Excel.", "nivel": "bloqueado"}

    if politica.metodo_preferido == PoliticaExtraccionFuente.METODO_CSV_EXCEL or conector.fuente_autorizo_uso:
        return {"valido": True, "mensaje": "Conector catalogo CSV/Excel valido.", "nivel": "ok"}

    politica_base = validar_conector_segun_politica(conector)
    if politica_base["nivel"] == "bloqueado":
        return politica_base
    return {"valido": True, "mensaje": "Conector catalogo valido con revision manual.", "nivel": "advertencia"}


def descargar_archivo_catalogo(conector):
    validacion = validar_conector_catalogo(conector)
    if not validacion["valido"]:
        return {"ok": False, "error": validacion["mensaje"], "importacion": None}
    if conector.tipo_conector not in TIPOS_REMOTOS:
        return {"ok": False, "error": "El conector no es remoto.", "importacion": None}

    try:
        response = requests.get(conector.url_recurso, timeout=20, allow_redirects=True, stream=True)
    except requests.RequestException as exc:
        return {"ok": False, "error": f"No se pudo descargar catalogo: {exc}", "importacion": None}

    if response.status_code >= 400:
        return {"ok": False, "error": f"Descarga rechazada con status {response.status_code}.", "importacion": None}

    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    extension = _extension_url(conector.url_recurso)
    formato = _formato_definido(conector)
    if "html" in content_type or extension in {".html", ".htm"}:
        return {"ok": False, "error": "La respuesta parece HTML, no catalogo CSV/Excel.", "importacion": None}
    if content_type and content_type not in CONTENT_TYPES_PERMITIDOS and formato == ConectorFuente.FORMATO_DESCONOCIDO:
        return {"ok": False, "error": f"Content-Type no compatible: {content_type}.", "importacion": None}

    contenido = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        contenido.extend(chunk)
        if len(contenido) > MAX_BYTES:
            return {"ok": False, "error": "El archivo supera el maximo de 10 MB.", "importacion": None}

    if not contenido:
        return {"ok": False, "error": "El archivo descargado esta vacio.", "importacion": None}

    extension = extension if extension in EXTENSIONES else f".{formato}"
    nombre = f"catalogo_{conector.pk}{extension}"
    importacion = ImportacionProductos(
        fuente_web=conector.fuente_web,
        conector=conector,
        tipo_archivo=EXTENSIONES.get(extension, formato),
        estado=ImportacionProductos.ESTADO_PENDIENTE,
        observaciones=f"Archivo descargado por conector {conector.nombre}.",
    )
    importacion.archivo.save(nombre, ContentFile(bytes(contenido)), save=True)
    importacion.tipo_archivo = detectar_tipo_archivo(importacion.archivo)
    importacion.save(update_fields=["tipo_archivo"])
    return {"ok": True, "error": None, "importacion": importacion}


def ejecutar_conector_catalogo(conector):
    ejecucion = crear_ejecucion_conector(conector)
    validacion = validar_conector_catalogo(conector)
    if not validacion["valido"]:
        registrar_detalle_ejecucion(ejecucion, "error", validacion["mensaje"])
        return finalizar_ejecucion_conector(ejecucion, {"errores": 1, "mensaje": validacion["mensaje"]})

    importacion = None
    if conector.tipo_conector in TIPOS_REMOTOS:
        descarga = descargar_archivo_catalogo(conector)
        if not descarga["ok"]:
            registrar_detalle_ejecucion(ejecucion, "error", descarga["error"])
            return finalizar_ejecucion_conector(ejecucion, {"errores": 1, "mensaje": descarga["error"]})
        importacion = descarga["importacion"]
    else:
        importacion = (
            conector.importaciones.filter(estado=ImportacionProductos.ESTADO_PENDIENTE)
            .order_by("fecha_creacion", "id")
            .first()
        )
        if not importacion:
            mensaje = "Conector manual sin importaciones pendientes. Cargar un CSV/Excel y asociarlo al conector."
            registrar_detalle_ejecucion(ejecucion, "omitido", mensaje)
            return finalizar_ejecucion_conector(ejecucion, {"mensaje": mensaje, "log_resumido": mensaje})

    procesar_importacion(importacion)
    registrar_detalle_ejecucion(
        ejecucion,
        "procesado" if importacion.errores == 0 else "error",
        f"Importacion #{importacion.pk} procesada con estado {importacion.estado}.",
        datos_originales=f"importacion_id={importacion.pk}",
    )
    return finalizar_ejecucion_conector(
        ejecucion,
        {
            "productos_detectados": importacion.total_filas,
            "productos_creados": importacion.productos_creados,
            "productos_actualizados": importacion.productos_actualizados,
            "precios_creados": importacion.precios_creados,
            "errores": importacion.errores,
            "mensaje": f"Importacion #{importacion.pk} procesada.",
            "log_resumido": importacion.mensaje_error or "",
        },
    )
