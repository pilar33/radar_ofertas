from decimal import Decimal

from django.utils import timezone

from oportunidades.models import PrecioFuente, ProductoFuente


def _ultimo_precio(producto_fuente):
    return producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()


def _precios(producto_fuente):
    return list(producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id"))


def _nivel(score, requiere_revision=False):
    if requiere_revision:
        return ProductoFuente.NIVEL_REVISAR
    if score >= 75:
        return ProductoFuente.NIVEL_ALTO
    if score >= 50:
        return ProductoFuente.NIVEL_MEDIO
    return ProductoFuente.NIVEL_BAJO


def _descuento(precio):
    if not precio or not precio.precio_lista or not precio.precio_oportunidad:
        return Decimal("0.00")
    if precio.precio_lista <= 0:
        return Decimal("0.00")
    return ((precio.precio_lista - precio.precio_oportunidad) / precio.precio_lista * Decimal("100")).quantize(Decimal("0.01"))


def _promedio_historico(precios):
    valores = [p.precio_oportunidad or p.precio for p in precios if (p.precio_oportunidad or p.precio)]
    if not valores:
        return Decimal("0.00")
    return (sum(valores) / len(valores)).quantize(Decimal("0.01"))


def _comparacion_fuentes(producto_fuente, precio_actual):
    canonico = producto_fuente.producto_canonico
    if not canonico or not precio_actual:
        return {"cantidad": 0, "es_mejor": False, "diferencia_promedio": Decimal("0.00")}
    precios_actuales = []
    for aparicion in canonico.apariciones.prefetch_related("precios_fuente"):
        precio = _ultimo_precio(aparicion)
        if precio and precio.precio_oportunidad > 0:
            precios_actuales.append((aparicion, precio.precio_oportunidad))
    if not precios_actuales:
        return {"cantidad": 0, "es_mejor": False, "diferencia_promedio": Decimal("0.00")}
    minimo = min(valor for _, valor in precios_actuales)
    promedio = (sum(valor for _, valor in precios_actuales) / len(precios_actuales)).quantize(Decimal("0.01"))
    actual = precio_actual.precio_oportunidad or precio_actual.precio
    diferencia = Decimal("0.00")
    if promedio > 0:
        diferencia = ((promedio - actual) / promedio * Decimal("100")).quantize(Decimal("0.01"))
    return {"cantidad": len(precios_actuales), "es_mejor": actual == minimo, "diferencia_promedio": diferencia}


def calcular_score_comercial_producto_fuente(producto_fuente, guardar=True):
    precios = _precios(producto_fuente)
    precio = precios[0] if precios else None
    score = 0
    motivos = []
    componentes = {}

    if not precio:
        score -= 20
        motivos.append("Sin historial de precios.")
        componentes["historial"] = 0
    else:
        descuento = _descuento(precio)
        componentes["descuento"] = str(descuento)
        if precio.precio_transferencia > 0:
            score += 15
            motivos.append("Tiene precio por transferencia.")
        if precio.precio_tarjeta > 0:
            score += 5
            motivos.append("Tiene dato de tarjeta/cuotas.")
        if precio.precio_oportunidad > 0:
            score += 10
        else:
            score -= 25
            motivos.append("Precio oportunidad no valido.")
        if descuento > 0:
            score += min(25, int(descuento))
            motivos.append(f"Descuento estimado {descuento}%.")
        if len(precios) >= 2:
            score += 8
            promedio = _promedio_historico(precios)
            anterior = precios[1].precio_oportunidad or precios[1].precio
            actual = precio.precio_oportunidad or precio.precio
            if promedio and actual < promedio:
                score += 8
                motivos.append("Ultimo precio menor al promedio historico.")
            if anterior and actual < anterior:
                score += 8
                motivos.append("Ultimo precio bajo frente al anterior.")
            componentes["promedio_historico"] = str(promedio)
        else:
            score -= 5
            motivos.append("Historial corto.")

    comparacion = _comparacion_fuentes(producto_fuente, precio)
    componentes["comparacion_fuentes"] = comparacion["cantidad"]
    if comparacion["cantidad"] > 1:
        score += 8
        if comparacion["es_mejor"]:
            score += 12
            motivos.append("Es la mejor fuente para el canonico.")
        if comparacion["diferencia_promedio"] > 0:
            score += min(10, int(comparacion["diferencia_promedio"]))
            motivos.append("Precio favorable contra promedio de fuentes.")

    if producto_fuente.imagen_url:
        score += 8
    else:
        score -= 10
        motivos.append("Sin imagen.")
    if producto_fuente.url_tecnica_generada:
        score -= 20
        motivos.append("URL tecnica, requiere revisar URL real.")
    elif producto_fuente.url_producto:
        score += 8
    if len((producto_fuente.titulo_original or "").strip()) >= 8:
        score += 4
    politica = getattr(producto_fuente.fuente_web, "politica_extraccion", None)
    if politica and politica.semaforo in {"verde", "amarillo"}:
        score += 8
    else:
        score -= 10
        motivos.append("Fuente sin semaforo confiable.")
    if producto_fuente.requiere_revision:
        score -= 20
        motivos.append("Marcado para revision.")
    if producto_fuente.descartado_curaduria:
        score -= 30
        motivos.append("Descartado en curaduria.")

    score = max(0, min(100, score))
    nivel = _nivel(score, producto_fuente.requiere_revision)
    motivo = " ".join(motivos) or "Score comercial calculado."
    if guardar:
        producto_fuente.score_comercial = score
        producto_fuente.nivel_oportunidad = nivel
        producto_fuente.motivo_score_comercial = motivo
        producto_fuente.fecha_score_comercial = timezone.now()
        producto_fuente.save(
            update_fields=[
                "score_comercial",
                "nivel_oportunidad",
                "motivo_score_comercial",
                "fecha_score_comercial",
                "fecha_actualizacion",
            ]
        )
    return {"score": score, "nivel": nivel, "motivo": motivo, "componentes": componentes, "precio": precio}


def recalcular_ranking_comercial(fuente_id=None, producto_fuente_id=None, solo_revisados=False, limite=None):
    qs = ProductoFuente.objects.select_related("fuente_web", "producto_canonico").prefetch_related("precios_fuente")
    if fuente_id:
        qs = qs.filter(fuente_web_id=fuente_id)
    if producto_fuente_id:
        qs = qs.filter(pk=producto_fuente_id)
    if solo_revisados:
        qs = qs.filter(revisado=True)
    if limite:
        qs = qs[: int(limite)]
    resultados = []
    for producto in qs:
        resultados.append((producto, calcular_score_comercial_producto_fuente(producto)))
    return resultados
