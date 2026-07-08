import csv
import io
import zipfile

from django.db.models import Q

from oportunidades.models import LoteCaptura, PrecioFuente, ProductoFuente, ResultadoExtraccionWeb, SugerenciaMatchingProducto


def _ultimo_precio(producto_fuente):
    return producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()


def exportar_dataset_productos_csv(output=None, delimiter=",", incluir_lotes_excluidos=False):
    buffer = output or io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter)
    writer.writerow(
        [
            "producto_canonico_id",
            "grupo_canonico_nombre",
            "cantidad_fuentes_canonico",
            "fuente_mas_barata",
            "precio_minimo_oportunidad",
            "precio_promedio_oportunidad",
            "diferencia_pct_min_promedio",
            "score_matching",
            "tiene_matching_aceptado",
            "requiere_revision_matching",
            "nombre_normalizado",
            "categoria",
            "producto_fuente_id",
            "titulo_original",
            "fuente",
            "url_producto",
            "imagen_url",
            "precio_lista",
            "precio_transferencia",
            "precio_tarjeta",
            "cuotas_texto",
            "precio_oportunidad",
            "tipo_precio_oportunidad",
            "fecha_precio",
            "score_comercial",
            "score_demanda_actual",
            "nivel_demanda_actual",
            "motivo_demanda_actual",
            "cantidad_vendida_visible",
            "texto_vendidos",
            "cantidad_resenas",
            "cantidad_preguntas",
            "calificacion",
            "stock_visible",
            "variacion_stock",
            "etiqueta_mas_vendido",
            "etiqueta_destacado",
            "etiqueta_tendencia",
            "cantidad_fuentes_donde_aparece",
            "requiere_revision",
            "revisado",
            "lote_captura_id",
            "lote_nombre",
            "lote_origen",
            "lote_tipo_carga",
            "lote_fecha_inicio",
            "lote_fecha_relevamiento",
            "lote_apto_dataset",
            "lote_excluir_ml",
            "lote_url_origen",
            "candidato_compra_id", "candidato_estado", "candidato_prioridad",
            "candidato_fecha_deteccion", "candidato_motivo", "fue_comprado",
            "cantidad_comprada_total", "precio_promedio_compra", "inversion_total",
            "fue_publicado", "canales_publicacion", "fue_vendido", "cantidad_vendida_total",
            "precio_promedio_venta", "ingreso_total", "ganancia_neta_total", "margen_real_pct",
            "dias_hasta_primera_venta", "dias_hasta_venta_total", "estado_resultado_comercial",
            "aprendizaje_comercial", "resultado_positivo",
        ]
    )
    productos = ProductoFuente.objects.select_related("producto_canonico__categoria", "fuente_web", "lote_origen").prefetch_related(
        "precios_fuente__lote_captura", "senales_demanda", "candidaturas_compra__resultado_comercial",
        "candidaturas_compra__compras__publicaciones",
    )
    for producto in productos:
        precio = _ultimo_precio(producto)
        lote = precio.lote_captura if precio and precio.lote_captura_id else producto.lote_origen
        if lote and lote.excluir_ml and not incluir_lotes_excluidos:
            continue
        canonico = producto.producto_canonico
        comparacion = canonico.comparaciones.order_by("-fecha_calculo", "-id").first() if canonico else None
        matching = SugerenciaMatchingProducto.objects.filter(Q(producto_a=producto) | Q(producto_b=producto)).order_by("-score", "-fecha_creacion").first()
        cantidad_fuentes = canonico.apariciones.values("fuente_web_id").distinct().count() if canonico else 0
        senal = producto.senales_demanda.order_by("-fecha_relevamiento", "-id").first()
        candidato = producto.candidaturas_compra.order_by("-fecha_deteccion", "-id").first()
        resultado = getattr(candidato, "resultado_comercial", None) if candidato else None
        publicaciones = []
        if candidato:
            publicaciones = list(candidato.compras.values_list("publicaciones__canal", flat=True).exclude(publicaciones__canal__isnull=True).distinct())
        if resultado and resultado.estado_resultado == resultado.ESTADO_VENDIDO_CON_GANANCIA and resultado.margen_real_pct > 0:
            resultado_positivo = True
        elif resultado and resultado.estado_resultado in {
            resultado.ESTADO_VENDIDO_CON_PERDIDA, resultado.ESTADO_VENDIDO_SIN_GANANCIA, resultado.ESTADO_DESCARTADO,
        }:
            resultado_positivo = False
        else:
            resultado_positivo = ""
        writer.writerow(
            [
                canonico.pk if canonico else "",
                canonico.nombre_normalizado if canonico else "",
                cantidad_fuentes,
                comparacion.fuente_mas_barata.nombre if comparacion and comparacion.fuente_mas_barata else "",
                comparacion.precio_minimo_oportunidad if comparacion else "",
                comparacion.precio_promedio_oportunidad if comparacion else "",
                comparacion.diferencia_pct_min_promedio if comparacion else "",
                matching.score if matching else "",
                bool(matching and matching.estado == SugerenciaMatchingProducto.ESTADO_ACEPTADA),
                bool(matching and matching.estado == SugerenciaMatchingProducto.ESTADO_PENDIENTE),
                canonico.nombre_normalizado if canonico else "",
                canonico.categoria.nombre if canonico and canonico.categoria_id else "",
                producto.pk,
                producto.titulo_original,
                producto.fuente_web.nombre,
                producto.url_producto,
                producto.imagen_url or "",
                precio.precio_lista if precio else "",
                precio.precio_transferencia if precio else "",
                precio.precio_tarjeta if precio else "",
                precio.cuotas_texto if precio else "",
                precio.precio_oportunidad if precio else "",
                precio.tipo_precio_oportunidad if precio else "",
                precio.fecha_relevamiento.isoformat() if precio else "",
                producto.score_comercial,
                producto.score_demanda_actual,
                producto.nivel_demanda_actual,
                producto.motivo_demanda_actual or "",
                senal.cantidad_vendida_visible if senal else 0,
                senal.texto_vendidos if senal else "",
                senal.cantidad_resenas if senal else 0,
                senal.cantidad_preguntas if senal else 0,
                senal.calificacion if senal else 0,
                senal.stock_visible if senal else 0,
                senal.variacion_stock if senal else 0,
                senal.etiqueta_mas_vendido if senal else False,
                senal.etiqueta_destacado if senal else False,
                senal.etiqueta_tendencia if senal else False,
                senal.cantidad_fuentes_donde_aparece if senal else cantidad_fuentes,
                producto.requiere_revision,
                producto.revisado,
                lote.pk if lote else "",
                lote.nombre if lote else "",
                lote.origen if lote else "",
                lote.tipo_carga if lote else "",
                lote.fecha_inicio.isoformat() if lote else "",
                lote.fecha_relevamiento.isoformat() if lote and lote.fecha_relevamiento else "",
                lote.apto_dataset if lote else "",
                lote.excluir_ml if lote else "",
                lote.url_origen if lote else "",
                candidato.pk if candidato else "", candidato.estado if candidato else "",
                candidato.prioridad if candidato else "", candidato.fecha_deteccion.isoformat() if candidato and candidato.fecha_deteccion else "",
                (candidato.motivo_candidato or candidato.motivo or "") if candidato else "",
                bool(resultado and resultado.cantidad_comprada_total), resultado.cantidad_comprada_total if resultado else 0,
                resultado.precio_promedio_compra if resultado else 0, resultado.inversion_total if resultado else 0,
                bool(publicaciones), "|".join(publicaciones), bool(resultado and resultado.cantidad_vendida_total),
                resultado.cantidad_vendida_total if resultado else 0, resultado.precio_promedio_venta if resultado else 0,
                resultado.ingreso_total if resultado else 0, resultado.ganancia_neta_total if resultado else 0,
                resultado.margen_real_pct if resultado else 0, resultado.dias_hasta_primera_venta if resultado else "",
                resultado.dias_hasta_venta_total if resultado else "", resultado.estado_resultado if resultado else "",
                resultado.aprendizaje if resultado else "", resultado_positivo,
            ]
        )
    return buffer


def exportar_lote_captura_csv(lote, output=None, delimiter=","):
    buffer = output or io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter)
    writer.writerow([
        "producto", "fuente", "url", "imagen", "precio_lista", "precio_transferencia",
        "precio_tarjeta", "precio_oportunidad", "tipo_oportunidad", "score_demanda",
        "score_comercial", "fecha_captura", "estado_revision",
    ])
    productos = ProductoFuente.objects.filter(
        Q(lote_origen=lote) | Q(precios_fuente__lote_captura=lote) | Q(detallelotecaptura__lote=lote)
    ).select_related("fuente_web").distinct()
    for producto in productos:
        precio = producto.precios_fuente.filter(lote_captura=lote).order_by("-fecha_relevamiento", "-id").first() or _ultimo_precio(producto)
        writer.writerow([
            producto.titulo_original, producto.fuente_web.nombre, producto.url_producto,
            producto.imagen_url or "", precio.precio_lista if precio else "",
            precio.precio_transferencia if precio else "", precio.precio_tarjeta if precio else "",
            precio.precio_oportunidad if precio else "", precio.tipo_precio_oportunidad if precio else "",
            producto.score_demanda_actual, producto.score_comercial, lote.fecha_relevamiento or lote.fecha_inicio,
            "revisado" if producto.revisado else "requiere_revision" if producto.requiere_revision else "pendiente",
        ])
    return buffer


def exportar_historial_precios_csv(output=None, delimiter=","):
    buffer = output or io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter)
    writer.writerow(
        [
            "producto_fuente_id",
            "fuente",
            "titulo",
            "fecha",
            "precio",
            "precio_lista",
            "precio_transferencia",
            "precio_tarjeta",
            "precio_oportunidad",
            "tipo_precio_oportunidad",
        ]
    )
    precios = PrecioFuente.objects.select_related("producto_fuente__fuente_web").order_by("producto_fuente_id", "fecha_relevamiento")
    for precio in precios:
        writer.writerow(
            [
                precio.producto_fuente_id,
                precio.producto_fuente.fuente_web.nombre,
                precio.producto_fuente.titulo_original,
                precio.fecha_relevamiento.isoformat(),
                precio.precio,
                precio.precio_lista,
                precio.precio_transferencia,
                precio.precio_tarjeta,
                precio.precio_oportunidad,
                precio.tipo_precio_oportunidad,
            ]
        )
    return buffer


def exportar_resultados_preview_csv(output=None, delimiter=","):
    buffer = output or io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter)
    writer.writerow(["id", "fuente", "titulo", "precio_oportunidad", "url_producto", "imagen_url", "estado", "producto_fuente_id"])
    resultados = ResultadoExtraccionWeb.objects.select_related("ejecucion__conector__fuente_web", "producto_fuente")
    for resultado in resultados:
        writer.writerow(
            [
                resultado.pk,
                resultado.ejecucion.conector.fuente_web.nombre,
                resultado.titulo or "",
                resultado.precio_oportunidad_decimal,
                resultado.url_producto or "",
                resultado.imagen_url or "",
                resultado.estado,
                resultado.producto_fuente_id or "",
            ]
        )
    return buffer


def exportar_dataset_completo_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archivo_zip:
        productos = exportar_dataset_productos_csv().getvalue()
        precios = exportar_historial_precios_csv().getvalue()
        previews = exportar_resultados_preview_csv().getvalue()
        archivo_zip.writestr("productos_dataset.csv", productos)
        archivo_zip.writestr("historial_precios.csv", precios)
        archivo_zip.writestr("resultados_preview.csv", previews)
    buffer.seek(0)
    return buffer
