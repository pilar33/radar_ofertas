from decimal import Decimal

from oportunidades.models import PrecioFuente, ProductoFuente
from oportunidades.services.precio_service import calcular_variacion_precio


def _ultimo_precio(producto_fuente):
    return producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()


def calcular_score_comercial_producto_fuente(producto_fuente, guardar=True):
    precio = _ultimo_precio(producto_fuente)
    score = 0
    motivos = []
    if not precio:
        motivos.append("Sin historial de precios.")
    else:
        if precio.precio_transferencia and precio.precio_transferencia > 0:
            score += 20
            motivos.append("Tiene precio por transferencia.")
        if precio.precio_lista and precio.precio_oportunidad and precio.precio_oportunidad < precio.precio_lista:
            score += 20
            motivos.append("Precio oportunidad menor que lista.")
            descuento = ((precio.precio_lista - precio.precio_oportunidad) / precio.precio_lista * Decimal("100")).quantize(Decimal("0.01"))
            if descuento >= Decimal("20.00"):
                score += 15
                motivos.append("Descuento alto.")
        if precio.precio_oportunidad and precio.precio_oportunidad > 0:
            score += 10
        else:
            score -= 25
            motivos.append("Precio oportunidad no valido.")
    if producto_fuente.imagen_url:
        score += 10
    else:
        score -= 10
        motivos.append("Sin imagen.")
    if producto_fuente.url_tecnica_generada:
        score -= 20
        motivos.append("URL tecnica, requiere revisar URL real.")
    elif producto_fuente.url_producto:
        score += 10
    politica = getattr(producto_fuente.fuente_web, "politica_extraccion", None)
    if politica and politica.semaforo in {"verde", "amarillo"}:
        score += 10
    else:
        score -= 10
        motivos.append("Fuente sin semaforo confiable.")
    if producto_fuente.requiere_revision:
        score -= 20
        motivos.append("Marcado para revision.")
    if producto_fuente.producto_canonico and producto_fuente.producto_canonico.apariciones.count() > 1:
        score += 10
        motivos.append("Comparable en mas de una aparicion.")
    score = max(0, min(100, score))
    motivo = " ".join(motivos) or "Score comercial calculado."
    if guardar:
        producto_fuente.score_comercial = score
        producto_fuente.motivo_score_comercial = motivo
        producto_fuente.save(update_fields=["score_comercial", "motivo_score_comercial", "fecha_actualizacion"])
    return {"score": score, "motivo": motivo, "precio": precio}


def recalcular_ranking_comercial():
    resultados = []
    for producto in ProductoFuente.objects.select_related("fuente_web", "producto_canonico").prefetch_related("precios_fuente"):
        resultados.append((producto, calcular_score_comercial_producto_fuente(producto)))
    return resultados
