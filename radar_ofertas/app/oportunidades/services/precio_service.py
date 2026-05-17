from decimal import Decimal


def _decimal(valor):
    return Decimal(str(valor or 0))


def obtener_ultimo_precio(producto):
    if not producto:
        return None

    return producto.precios.order_by("-fecha_relevamiento", "-id").first()


def obtener_precio_anterior(producto):
    if not producto:
        return None

    precios = list(producto.precios.order_by("-fecha_relevamiento", "-id")[:2])
    if len(precios) < 2:
        return None

    return precios[1]


def calcular_variacion_precio(producto):
    ultimo = obtener_ultimo_precio(producto)
    anterior = obtener_precio_anterior(producto)

    precio_actual = _decimal(ultimo.precio) if ultimo else Decimal("0")
    precio_anterior = _decimal(anterior.precio) if anterior else None
    diferencia = Decimal("0")
    porcentaje_variacion = Decimal("0")

    if precio_anterior and precio_anterior > 0:
        diferencia = precio_actual - precio_anterior
        porcentaje_variacion = (diferencia / precio_anterior * Decimal("100")).quantize(Decimal("0.01"))

    return {
        "precio_actual": precio_actual,
        "precio_anterior": precio_anterior,
        "diferencia": diferencia.quantize(Decimal("0.01")),
        "porcentaje_variacion": porcentaje_variacion,
    }


def obtener_precio_promedio(producto):
    if not producto:
        return Decimal("0")

    precios = [_decimal(precio) for precio in producto.precios.values_list("precio", flat=True)]
    if not precios:
        return Decimal("0")

    return (sum(precios) / Decimal(len(precios))).quantize(Decimal("0.01"))


def detectar_baja_precio(producto, umbral_porcentaje=10):
    variacion = calcular_variacion_precio(producto)
    precio_actual = variacion["precio_actual"]
    referencias = []

    if variacion["precio_anterior"]:
        referencias.append(variacion["precio_anterior"])

    promedio = obtener_precio_promedio(producto)
    if promedio > 0:
        referencias.append(promedio)

    if precio_actual <= 0 or not referencias:
        return False

    umbral = Decimal(str(umbral_porcentaje or 0)) / Decimal("100")
    for referencia in referencias:
        if referencia > 0 and precio_actual <= referencia * (Decimal("1") - umbral):
            return True

    return False
