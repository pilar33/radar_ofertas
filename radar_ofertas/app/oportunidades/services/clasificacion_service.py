from decimal import Decimal

from .margen_service import calcular_resultado_comercial


def _decimal(valor):
    return Decimal(str(valor or 0))


def _clamp(valor, minimo=0, maximo=100):
    return max(minimo, min(maximo, int(valor)))


def clasificar_oportunidad(producto, precio_actual, precio_reventa_estimado=None, costo_envio=0):
    precio_actual = _decimal(precio_actual)

    if not producto or precio_actual <= 0:
        return {
            "tipo": "descartar",
            "riesgo": "alto",
            "puntaje": 0,
            "motivo": "Faltan datos o el precio actual no es valido. No conviene priorizarlo.",
            "margen_estimado": Decimal("0.00"),
            "porcentaje_margen": Decimal("0.00"),
            "precio_reventa_estimado": Decimal("0.00"),
        }

    resultado = calcular_resultado_comercial(
        precio_actual,
        precio_reventa_estimado=precio_reventa_estimado,
        costo_envio=costo_envio,
    )
    margen = resultado["margen_estimado"]
    porcentaje = resultado["porcentaje_margen"]

    puntaje = 0

    if porcentaje >= 25:
        puntaje += 30
    if porcentaje >= 40:
        puntaje += 15
    if producto.es_chico_liviano:
        puntaje += 15
    else:
        puntaje -= 10
    if producto.es_fragil:
        puntaje -= 20
    else:
        puntaje += 10
    if getattr(producto.fuente, "activa", False):
        puntaje += 5
    if getattr(producto.categoria, "activa", False):
        puntaje += 5
    if precio_actual > 0:
        puntaje += 10
    if not producto.vendedor:
        puntaje -= 5
    if porcentaje < 10:
        puntaje -= 20
    if margen < 0:
        puntaje -= 40

    puntaje = _clamp(puntaje)

    if margen < 0 or (producto.es_fragil and porcentaje < 25):
        tipo = "descartar"
        riesgo = "alto"
        motivo = "Faltan datos o el margen es bajo. No conviene priorizarlo."
        puntaje = min(puntaje, 49)
    elif porcentaje >= 25 and producto.es_chico_liviano and not producto.es_fragil:
        tipo = "reventa"
        riesgo = "bajo" if porcentaje >= 40 else "medio"
        motivo = "Producto chico, no fragil y con margen estimado superior al 25%. Puede evaluarse para reventa."
        puntaje = max(75, puntaje)
    elif margen > 0:
        tipo = "afiliado"
        riesgo = "medio"
        motivo = "Producto util para contenido, pero el margen no justifica comprar stock. Conviene usarlo como afiliado."
        puntaje = min(80, max(50, puntaje))
    else:
        tipo = "descartar"
        riesgo = "alto"
        motivo = "Faltan datos o el margen es bajo. No conviene priorizarlo."
        puntaje = min(puntaje, 49)

    return {
        "tipo": tipo,
        "riesgo": riesgo,
        "puntaje": puntaje,
        "motivo": motivo,
        "margen_estimado": margen,
        "porcentaje_margen": porcentaje,
        "precio_reventa_estimado": resultado["precio_reventa_estimado"],
    }
