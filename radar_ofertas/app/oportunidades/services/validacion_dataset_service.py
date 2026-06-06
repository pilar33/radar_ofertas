from django.db.models import Count

from oportunidades.models import FuenteWeb, PrecioFuente, ProductoCanonico, ProductoFuente


def _ultimo_precio(producto):
    return producto.precios_fuente.order_by("-fecha_relevamiento", "-id").first()


def _tiene_url_real(producto):
    url = (producto.url_producto or "").strip().lower()
    return bool(url.startswith("http://") or url.startswith("https://")) and not producto.url_tecnica_generada


def validar_dataset_piloto():
    productos = ProductoFuente.objects.select_related("fuente_web", "producto_canonico").prefetch_related("precios_fuente")
    total_productos = productos.count()
    total_canonicos = ProductoCanonico.objects.count()
    total_precios = PrecioFuente.objects.count()
    total_fuentes = FuenteWeb.objects.count()

    productos_sin_url = []
    productos_url_tecnica = []
    productos_sin_imagen = []
    productos_sin_precio_oportunidad = []
    productos_con_transferencia = []
    productos_lista_mayor_transferencia = []
    productos_requieren_revision = []

    for producto in productos:
        precio = _ultimo_precio(producto)
        if not _tiene_url_real(producto):
            productos_sin_url.append(producto)
        if producto.url_tecnica_generada:
            productos_url_tecnica.append(producto)
        if not producto.imagen_url:
            productos_sin_imagen.append(producto)
        if not precio or not precio.precio_oportunidad or precio.precio_oportunidad <= 0:
            productos_sin_precio_oportunidad.append(producto)
        if precio and precio.precio_transferencia and precio.precio_transferencia > 0:
            productos_con_transferencia.append(producto)
        if (
            precio
            and precio.precio_lista
            and precio.precio_transferencia
            and precio.precio_lista > precio.precio_transferencia
        ):
            productos_lista_mayor_transferencia.append(producto)
        if producto.requiere_revision:
            productos_requieren_revision.append(producto)

    duplicados_probables = (
        ProductoFuente.objects.values("fuente_web_id", "titulo_original")
        .annotate(cantidad=Count("id"))
        .filter(cantidad__gt=1)
        .count()
    )

    con_imagen = total_productos - len(productos_sin_imagen)
    con_url_real = total_productos - len(productos_sin_url)
    con_precio_oportunidad = total_productos - len(productos_sin_precio_oportunidad)

    dataset_apto = (
        total_productos > 0
        and con_url_real > 0
        and con_imagen > 0
        and con_precio_oportunidad > 0
        and len(productos_requieren_revision) < total_productos
    )

    problemas = []
    if total_productos == 0:
        problemas.append("No hay productos procesados todavia.")
    if productos_sin_url:
        problemas.append("Hay productos sin URL real o con URL tecnica.")
    if productos_sin_imagen:
        problemas.append("Hay productos sin imagen.")
    if productos_sin_precio_oportunidad:
        problemas.append("Hay productos sin precio oportunidad.")
    if duplicados_probables:
        problemas.append("Hay duplicados probables por fuente y titulo.")
    if productos_requieren_revision:
        problemas.append("Hay productos que requieren revision de curaduria.")

    return {
        "total_productos": total_productos,
        "total_canonicos": total_canonicos,
        "total_precios": total_precios,
        "total_fuentes": total_fuentes,
        "sin_url": len(productos_sin_url),
        "url_tecnica": len(productos_url_tecnica),
        "sin_imagen": len(productos_sin_imagen),
        "sin_precio_oportunidad": len(productos_sin_precio_oportunidad),
        "con_transferencia": len(productos_con_transferencia),
        "lista_mayor_transferencia": len(productos_lista_mayor_transferencia),
        "requieren_revision": len(productos_requieren_revision),
        "duplicados_probables": duplicados_probables,
        "con_imagen": con_imagen,
        "con_url_real": con_url_real,
        "con_precio_oportunidad": con_precio_oportunidad,
        "dataset_apto": dataset_apto,
        "problemas": problemas,
        "muestras": {
            "sin_url": productos_sin_url[:10],
            "sin_imagen": productos_sin_imagen[:10],
            "sin_precio_oportunidad": productos_sin_precio_oportunidad[:10],
            "requieren_revision": productos_requieren_revision[:10],
        },
    }
