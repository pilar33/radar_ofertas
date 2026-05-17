from decimal import Decimal


def calcular_margen(precio_compra, precio_reventa_estimado, costo_envio=0, costo_embalaje=0):
    precio_compra = Decimal(precio_compra or 0)
    precio_reventa_estimado = Decimal(precio_reventa_estimado or 0)
    costo_envio = Decimal(costo_envio or 0)
    costo_embalaje = Decimal(costo_embalaje or 0)

    costo_total = precio_compra + costo_envio + costo_embalaje
    margen = precio_reventa_estimado - costo_total
    porcentaje = Decimal("0")

    if costo_total > 0:
        porcentaje = (margen / costo_total) * Decimal("100")

    return {
        "costo_total": costo_total,
        "margen": margen,
        "porcentaje": porcentaje,
    }
