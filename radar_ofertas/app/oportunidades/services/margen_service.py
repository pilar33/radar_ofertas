from decimal import Decimal


DOS_DECIMALES = Decimal("0.01")


def _decimal(valor):
    return Decimal(str(valor or 0))


def _redondear(valor):
    return _decimal(valor).quantize(DOS_DECIMALES)


def calcular_margen(precio_compra, precio_reventa_estimado, costo_envio=0, costo_embalaje=0, otros_costos=0):
    costo_total = (
        _decimal(precio_compra)
        + _decimal(costo_envio)
        + _decimal(costo_embalaje)
        + _decimal(otros_costos)
    )
    margen = _decimal(precio_reventa_estimado) - costo_total
    return _redondear(margen)


def calcular_porcentaje_margen(precio_compra, margen):
    precio_compra = _decimal(precio_compra)
    margen = _decimal(margen)

    if precio_compra <= 0:
        return Decimal("0.00")

    return _redondear((margen / precio_compra) * Decimal("100"))


def estimar_precio_reventa(precio_compra, porcentaje_objetivo=35):
    precio_compra = _decimal(precio_compra)
    porcentaje_objetivo = _decimal(porcentaje_objetivo)

    if precio_compra <= 0:
        return Decimal("0.00")

    factor = Decimal("1") + (porcentaje_objetivo / Decimal("100"))
    return _redondear(precio_compra * factor)


def calcular_resultado_comercial(
    precio_compra,
    precio_reventa_estimado=None,
    costo_envio=0,
    costo_embalaje=0,
    otros_costos=0,
):
    precio_compra = _redondear(precio_compra)
    if precio_reventa_estimado is None or _decimal(precio_reventa_estimado) <= 0:
        precio_reventa_estimado = estimar_precio_reventa(precio_compra)
    else:
        precio_reventa_estimado = _redondear(precio_reventa_estimado)

    margen_estimado = calcular_margen(
        precio_compra,
        precio_reventa_estimado,
        costo_envio=costo_envio,
        costo_embalaje=costo_embalaje,
        otros_costos=otros_costos,
    )
    porcentaje_margen = calcular_porcentaje_margen(precio_compra, margen_estimado)

    return {
        "precio_compra": precio_compra,
        "precio_reventa_estimado": precio_reventa_estimado,
        "margen_estimado": margen_estimado,
        "porcentaje_margen": porcentaje_margen,
    }
