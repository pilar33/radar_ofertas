from .margen_service import calcular_margen


def clasificar_oportunidad(producto, precio_actual, precio_reventa_estimado):
    if not producto or not precio_actual or not precio_reventa_estimado:
        return {
            "tipo": "descartar",
            "riesgo": "alto",
            "puntaje": 0,
            "motivo": "Faltan datos para evaluar la oportunidad.",
            "margen_estimado": 0,
            "porcentaje_margen": 0,
        }

    margen = calcular_margen(precio_actual, precio_reventa_estimado)
    porcentaje = margen["porcentaje"]

    if porcentaje >= 25 and producto.es_chico_liviano and not producto.es_fragil:
        tipo = "reventa"
        riesgo = "bajo"
        motivo = "Buen margen, producto chico y bajo riesgo logistico."
        puntaje = min(100, int(porcentaje) + 40)
    elif porcentaje < 25 and precio_actual > 0:
        tipo = "afiliado"
        riesgo = "medio"
        motivo = "Margen moderado; conviene validar como contenido o afiliado."
        puntaje = min(75, max(20, int(porcentaje) + 20))
    else:
        tipo = "descartar"
        riesgo = "alto"
        motivo = "La relacion precio/riesgo no justifica avanzar."
        puntaje = 0

    if riesgo == "alto":
        tipo = "descartar"

    return {
        "tipo": tipo,
        "riesgo": riesgo,
        "puntaje": puntaje,
        "motivo": motivo,
        "margen_estimado": margen["margen"],
        "porcentaje_margen": porcentaje,
    }
