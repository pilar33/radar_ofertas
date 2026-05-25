from decimal import Decimal

from oportunidades.models import ComparacionPrecio


def obtener_precios_actuales_por_fuente(producto_canonico):
    precios = []
    apariciones = producto_canonico.apariciones.select_related("fuente_web").prefetch_related("precios_fuente")
    for producto_fuente in apariciones:
        ultimo_precio = producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()
        if ultimo_precio:
            precios.append((producto_fuente, ultimo_precio))
    return precios


def detectar_fuente_mas_barata(producto_canonico):
    precios = obtener_precios_actuales_por_fuente(producto_canonico)
    if not precios:
        return None
    producto_fuente, _ = min(precios, key=lambda item: item[1].precio)
    return producto_fuente.fuente_web


def calcular_diferencia_min_promedio(precio_minimo, precio_promedio):
    precio_minimo = Decimal(precio_minimo or 0)
    precio_promedio = Decimal(precio_promedio or 0)
    if precio_promedio <= 0:
        return Decimal("0.00")
    return ((precio_promedio - precio_minimo) / precio_promedio * Decimal("100")).quantize(Decimal("0.01"))


def calcular_comparacion_producto(producto_canonico):
    precios = obtener_precios_actuales_por_fuente(producto_canonico)
    valores = [precio.precio for _, precio in precios]
    if not valores:
        return ComparacionPrecio.objects.create(producto_canonico=producto_canonico)

    precio_minimo = min(valores)
    precio_maximo = max(valores)
    precio_promedio = (sum(valores) / Decimal(len(valores))).quantize(Decimal("0.01"))
    fuente_mas_barata = detectar_fuente_mas_barata(producto_canonico)

    return ComparacionPrecio.objects.create(
        producto_canonico=producto_canonico,
        precio_minimo=precio_minimo,
        precio_maximo=precio_maximo,
        precio_promedio=precio_promedio,
        cantidad_fuentes=len({producto_fuente.fuente_web_id for producto_fuente, _ in precios}),
        fuente_mas_barata=fuente_mas_barata,
        diferencia_porcentual_min_promedio=calcular_diferencia_min_promedio(precio_minimo, precio_promedio),
    )
