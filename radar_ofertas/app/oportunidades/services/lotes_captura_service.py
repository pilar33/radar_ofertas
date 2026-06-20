import json

from django.db.models import Q
from django.utils import timezone

from oportunidades.models import DetalleLoteCaptura, LoteCaptura


def _serializar(valor):
    if valor in (None, ""):
        return valor
    if isinstance(valor, str):
        return valor
    return json.dumps(valor, ensure_ascii=False, default=str)


def _nombre_automatico(fuente_web, url_categoria, url_origen):
    fuente = fuente_web.nombre if fuente_web else "Captura"
    categoria = (url_categoria or url_origen or "").rstrip("/").split("/")[-1] or "general"
    return f"{fuente} - {categoria} - {timezone.localtime():%Y-%m-%d %H:%M}"


def crear_lote_captura(
    origen,
    fuente_web=None,
    conector=None,
    extractor=None,
    importacion=None,
    sesion_laboratorio=None,
    ejecucion_conector=None,
    url_origen=None,
    url_categoria=None,
    tipo_carga=LoteCaptura.TIPO_PILOTO,
    observaciones=None,
    usuario_texto=None,
    parametros=None,
    nombre=None,
    estado=LoteCaptura.ESTADO_EJECUTANDO,
):
    return LoteCaptura.objects.create(
        nombre=nombre or _nombre_automatico(fuente_web, url_categoria, url_origen),
        origen=origen,
        fuente_web=fuente_web,
        conector=conector,
        extractor=extractor,
        importacion=importacion,
        sesion_laboratorio=sesion_laboratorio,
        ejecucion_conector=ejecucion_conector,
        url_origen=url_origen,
        url_categoria=url_categoria,
        tipo_carga=tipo_carga,
        observaciones=observaciones,
        usuario_texto=usuario_texto,
        parametros=_serializar(parametros),
        estado=estado,
        fecha_relevamiento=timezone.now(),
    )


def registrar_detalle_lote(
    lote,
    estado,
    producto_fuente=None,
    precio_fuente=None,
    resultado_extraccion=None,
    resultado_laboratorio=None,
    mensaje=None,
    datos_originales=None,
):
    return DetalleLoteCaptura.objects.create(
        lote=lote,
        estado=estado,
        producto_fuente=producto_fuente,
        precio_fuente=precio_fuente,
        resultado_extraccion=resultado_extraccion,
        resultado_laboratorio=resultado_laboratorio,
        mensaje=mensaje,
        datos_originales=_serializar(datos_originales),
    )


def recalcular_contadores_lote(lote):
    resultados_extraccion = lote.resultados_extraccion.all()
    resultados_laboratorio = lote.resultados_laboratorio.all()
    detalles = lote.detalles.all()
    detectados = resultados_extraccion.count() + resultados_laboratorio.count()
    seleccionados = resultados_extraccion.filter(seleccionado=True).count() + resultados_laboratorio.filter(seleccionado=True).count()
    procesados_resultados = resultados_extraccion.filter(estado="procesado").count()
    procesados_detalles = detalles.filter(estado=DetalleLoteCaptura.ESTADO_PROCESADO).count()
    errores_resultados = resultados_extraccion.filter(estado="error").count()
    errores_detalles = detalles.filter(estado=DetalleLoteCaptura.ESTADO_ERROR).count()
    incompletos = resultados_extraccion.filter(
        Q(procesable=False) | Q(titulo__isnull=True) | Q(titulo="") | Q(precio_oportunidad_decimal__lte=0)
    ).count()
    producto_ids = set(lote.productos_origen.values_list("id", flat=True))
    producto_ids.update(detalles.exclude(producto_fuente=None).values_list("producto_fuente_id", flat=True))
    lote.productos_detectados = detectados
    lote.productos_seleccionados = seleccionados
    lote.productos_procesados = max(procesados_resultados, procesados_detalles)
    lote.productos_creados = len(producto_ids)
    lote.productos_actualizados = detalles.filter(estado=DetalleLoteCaptura.ESTADO_PROCESADO, mensaje__icontains="actualizado").count()
    lote.precios_creados = lote.precios.count()
    lote.senales_demanda_creadas = lote.senales_demanda.count()
    lote.errores = max(errores_resultados, errores_detalles)
    lote.requiere_revision = bool(lote.errores or incompletos)
    lote.resumen = (
        f"{detectados} detectados, {lote.productos_procesados} procesados, "
        f"{lote.precios_creados} precios, {lote.senales_demanda_creadas} senales y {lote.errores} errores."
    )
    lote.save(update_fields=[
        "productos_detectados", "productos_seleccionados", "productos_procesados",
        "productos_creados", "productos_actualizados", "precios_creados",
        "senales_demanda_creadas", "errores", "requiere_revision", "resumen",
    ])
    return lote


def finalizar_lote_captura(lote, estado=LoteCaptura.ESTADO_PROCESADO):
    recalcular_contadores_lote(lote)
    if estado == LoteCaptura.ESTADO_PROCESADO and lote.errores:
        estado = LoteCaptura.ESTADO_PROCESADO_CON_ERRORES
    lote.estado = estado
    lote.fecha_fin = timezone.now()
    lote.save(update_fields=["estado", "fecha_fin"])
    return lote


def marcar_lote_descartado(lote, motivo):
    lote.estado = LoteCaptura.ESTADO_DESCARTADO
    lote.tipo_carga = LoteCaptura.TIPO_DESCARTE
    lote.apto_dataset = False
    lote.excluir_ml = True
    lote.motivo_exclusion = motivo
    lote.fecha_fin = lote.fecha_fin or timezone.now()
    lote.save(update_fields=["estado", "tipo_carga", "apto_dataset", "excluir_ml", "motivo_exclusion", "fecha_fin"])
    return lote


def marcar_lote_validado(lote):
    recalcular_contadores_lote(lote)
    lote.estado = LoteCaptura.ESTADO_VALIDADO
    lote.apto_dataset = not lote.errores
    lote.requiere_revision = bool(lote.errores)
    lote.fecha_fin = lote.fecha_fin or timezone.now()
    lote.save(update_fields=["estado", "apto_dataset", "requiere_revision", "fecha_fin"])
    return lote
