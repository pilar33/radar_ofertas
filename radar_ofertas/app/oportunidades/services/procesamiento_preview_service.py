import hashlib

from django.utils import timezone
from django.utils.text import slugify

from oportunidades.models import (
    DetalleEjecucionConector,
    PoliticaExtraccionFuente,
    PrecioFuente,
    Producto,
    ProductoFuente,
    ResultadoExtraccionWeb,
)
from oportunidades.services.comparacion_service import calcular_comparacion_producto
from oportunidades.services.evaluacion_multifuente_service import evaluar_producto_multifuente
from oportunidades.services.extractor_web_service import validar_ejecucion_extractor
from oportunidades.services.importacion_service import (
    crear_o_actualizar_producto_fuente,
    crear_precio_fuente,
    obtener_o_crear_categoria_desde_texto,
    obtener_o_crear_producto_canonico,
)
from oportunidades.services.normalizacion_service import normalizar_texto_producto


def _fuente_restringida_meli(fuente):
    politica = getattr(fuente, "politica_extraccion", None)
    return fuente.nombre.lower() == "mercado libre" and politica and politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_ROJO


def validar_resultado_procesable(resultado):
    if resultado.estado == ResultadoExtraccionWeb.ESTADO_PROCESADO or resultado.producto_fuente_id:
        return {"valido": False, "mensaje": "El resultado ya fue procesado.", "nivel": "bloqueado"}
    if not resultado.procesable:
        return {"valido": False, "mensaje": resultado.motivo_no_procesable or "Resultado marcado como no procesable.", "nivel": "bloqueado"}
    if not resultado.titulo:
        return {"valido": False, "mensaje": "Falta titulo.", "nivel": "bloqueado"}
    if not resultado.precio_decimal or resultado.precio_decimal <= 0:
        return {"valido": False, "mensaje": "Falta precio valido.", "nivel": "bloqueado"}
    if not (resultado.url_producto or resultado.fuente_url):
        return {"valido": False, "mensaje": "Falta URL de producto o fuente.", "nivel": "bloqueado"}
    if resultado.estado not in {ResultadoExtraccionWeb.ESTADO_DETECTADO, ResultadoExtraccionWeb.ESTADO_OMITIDO}:
        return {"valido": False, "mensaje": "Estado no habilitado para procesamiento.", "nivel": "bloqueado"}
    conector = resultado.ejecucion.conector
    if _fuente_restringida_meli(conector.fuente_web):
        return {"valido": False, "mensaje": "Mercado Libre esta restringido como fuente automatica.", "nivel": "bloqueado"}
    validacion = validar_ejecucion_extractor(conector)
    if not validacion["valido"]:
        return validacion
    return {"valido": True, "mensaje": "Resultado procesable.", "nivel": "ok"}


def _buscar_existente_por_preview(fuente, resultado):
    if resultado.url_producto:
        existente = ProductoFuente.objects.filter(fuente_web=fuente, url_producto=resultado.url_producto).first()
        if existente:
            return existente
    titulo_normalizado = normalizar_texto_producto(resultado.titulo)
    for producto in ProductoFuente.objects.filter(fuente_web=fuente):
        if normalizar_texto_producto(producto.titulo_original) == titulo_normalizado:
            return producto
    return None


def _identificador_preview(resultado):
    base = "|".join(
        [
            str(resultado.ejecucion.conector.fuente_web_id),
            normalizar_texto_producto(resultado.titulo),
            str(resultado.precio_oportunidad_decimal or resultado.precio_decimal or ""),
            str(resultado.fuente_url or ""),
        ]
    )
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def _url_producto_preview(fuente, resultado):
    if resultado.url_producto:
        return resultado.url_producto
    slug = slugify(resultado.titulo or "producto")[:60] or "producto"
    return f"{fuente.url_base.rstrip('/')}/radar-preview/{slug}-{_identificador_preview(resultado)}"


def procesar_resultado_preview(resultado, forzar_precio=False):
    validacion = validar_resultado_procesable(resultado)
    if not validacion["valido"]:
        resultado.procesable = False
        resultado.motivo_no_procesable = validacion["mensaje"]
        resultado.save(update_fields=["procesable", "motivo_no_procesable"])
        return {"ok": False, "mensaje": validacion["mensaje"], "producto_fuente": None, "precio_creado": False}

    conector = resultado.ejecucion.conector
    fuente = conector.fuente_web
    categoria = obtener_o_crear_categoria_desde_texto(None, None)
    row = {
        "titulo": resultado.titulo,
        "precio": resultado.precio_oportunidad_decimal or resultado.precio_decimal,
        "precio_lista": resultado.precio_lista_decimal,
        "precio_transferencia": resultado.precio_transferencia_decimal,
        "precio_tarjeta": resultado.precio_tarjeta_decimal,
        "cuotas_texto": resultado.cuotas_texto,
        "precio_oportunidad": resultado.precio_oportunidad_decimal,
        "tipo_precio_oportunidad": resultado.tipo_precio_oportunidad,
        "codigo_externo": f"preview-{_identificador_preview(resultado)}" if not resultado.url_producto else None,
        "url_producto": _url_producto_preview(fuente, resultado),
        "imagen_url": resultado.imagen_url,
        "descripcion": resultado.descripcion,
        "condicion": Producto.CONDICION_DESCONOCIDO,
        "moneda": fuente.moneda_principal,
        "origen_dato": PrecioFuente.ORIGEN_SCRAPING,
    }
    existente = _buscar_existente_por_preview(fuente, resultado)
    canonico, _ = obtener_o_crear_producto_canonico(row, categoria)
    if existente:
        producto_fuente, creado, actualizado = crear_o_actualizar_producto_fuente(row, fuente, categoria, canonico, actualizar=True)
    else:
        producto_fuente, creado, actualizado = crear_o_actualizar_producto_fuente(row, fuente, categoria, canonico, actualizar=True)
    precio, precio_creado = crear_precio_fuente(producto_fuente, row, crear_si_no_cambio=forzar_precio)
    calcular_comparacion_producto(canonico)
    evaluar_producto_multifuente(canonico)
    resultado.estado = ResultadoExtraccionWeb.ESTADO_PROCESADO
    resultado.producto_fuente = producto_fuente
    resultado.fecha_procesamiento = timezone.now()
    resultado.seleccionado = False
    resultado.save(update_fields=["estado", "producto_fuente", "fecha_procesamiento", "seleccionado"])
    DetalleEjecucionConector.objects.create(
        ejecucion=resultado.ejecucion,
        estado=DetalleEjecucionConector.ESTADO_PROCESADO,
        mensaje="Resultado preview procesado.",
        producto_fuente=producto_fuente,
        datos_originales=resultado.raw_data,
    )
    return {
        "ok": True,
        "mensaje": "Resultado procesado.",
        "producto_fuente": producto_fuente,
        "producto_creado": creado,
        "producto_actualizado": actualizado,
        "precio_creado": precio_creado,
        "precio": precio,
    }


def procesar_resultados_seleccionados(ejecucion, limite=20):
    total_seleccionados = ejecucion.resultados_web.filter(seleccionado=True).count()
    resultados = ejecucion.resultados_web.filter(seleccionado=True).order_by("id")[:limite]
    resumen = {"procesados": 0, "errores": 0, "omitidos": 0, "productos_creados": 0, "precios_creados": 0, "mensajes": []}
    for resultado in resultados:
        procesado = procesar_resultado_preview(resultado)
        if procesado["ok"]:
            resumen["procesados"] += 1
            resumen["productos_creados"] += int(bool(procesado.get("producto_creado")))
            resumen["precios_creados"] += int(bool(procesado.get("precio_creado")))
        else:
            resumen["errores"] += 1
            resumen["mensajes"].append(procesado["mensaje"])
    if total_seleccionados > limite:
        resumen["omitidos"] += total_seleccionados - limite
        resumen["mensajes"].append(f"Se omitieron {total_seleccionados - limite} por limite de seguridad.")
    ejecucion.productos_creados += resumen["productos_creados"]
    ejecucion.precios_creados += resumen["precios_creados"]
    ejecucion.errores += resumen["errores"]
    ejecucion.mensaje = f"Procesamiento seleccionados: {resumen['procesados']} procesados, {resumen['errores']} errores."
    ejecucion.save(update_fields=["productos_creados", "precios_creados", "errores", "mensaje"])
    return resumen


def marcar_resultado_seleccionado(resultado_id, seleccionado=True):
    resultado = ResultadoExtraccionWeb.objects.get(pk=resultado_id)
    resultado.seleccionado = seleccionado
    resultado.save(update_fields=["seleccionado"])
    return resultado
