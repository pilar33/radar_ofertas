import csv
import io
import zipfile

from django.db.models import Q

from oportunidades.models import PrecioFuente, ProductoFuente, ResultadoExtraccionWeb, SugerenciaMatchingProducto


def _ultimo_precio(producto_fuente):
    return producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()


def exportar_dataset_productos_csv(output=None, delimiter=","):
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
        ]
    )
    productos = ProductoFuente.objects.select_related("producto_canonico__categoria", "fuente_web").prefetch_related("precios_fuente", "senales_demanda")
    for producto in productos:
        precio = _ultimo_precio(producto)
        canonico = producto.producto_canonico
        comparacion = canonico.comparaciones.order_by("-fecha_calculo", "-id").first() if canonico else None
        matching = SugerenciaMatchingProducto.objects.filter(Q(producto_a=producto) | Q(producto_b=producto)).order_by("-score", "-fecha_creacion").first()
        cantidad_fuentes = canonico.apariciones.values("fuente_web_id").distinct().count() if canonico else 0
        senal = producto.senales_demanda.order_by("-fecha_relevamiento", "-id").first()
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
            ]
        )
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
