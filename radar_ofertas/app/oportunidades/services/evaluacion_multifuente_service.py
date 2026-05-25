from decimal import Decimal

from oportunidades.models import EvaluacionOportunidadMultifuente, PoliticaExtraccionFuente
from oportunidades.services.comparacion_service import calcular_comparacion_producto
from oportunidades.services.margen_service import calcular_resultado_comercial


def _clamp(valor):
    return max(0, min(100, int(valor)))


def calcular_indice_oportunidad(producto_canonico, producto_fuente):
    comparacion = producto_canonico.comparaciones.order_by("-fecha_calculo", "-id").first()
    ultimo_precio = producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()
    if not ultimo_precio:
        return 0

    precio = ultimo_precio.precio
    promedio = comparacion.precio_promedio if comparacion else Decimal("0")
    resultado = calcular_resultado_comercial(precio, precio_reventa_estimado=promedio or None)
    politica = getattr(producto_fuente.fuente_web, "politica_extraccion", None)
    descuento = ultimo_precio.descuento_porcentaje

    puntaje = 0
    if promedio and precio < promedio:
        puntaje += 20
    if resultado["porcentaje_margen"] >= 25:
        puntaje += 20
    if resultado["porcentaje_margen"] >= 40:
        puntaje += 15
    if producto_canonico.es_chico_liviano:
        puntaje += 10
    if not producto_canonico.es_fragil:
        puntaje += 10
    if politica and politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_VERDE:
        puntaje += 10
    if comparacion and comparacion.cantidad_fuentes >= 2:
        puntaje += 10
    if descuento >= 20:
        puntaje += 10
    if politica and politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_ROJO:
        puntaje -= 30
    if producto_canonico.es_fragil:
        puntaje -= 15
    if resultado["porcentaje_margen"] < 10:
        puntaje -= 20
    if not comparacion or comparacion.cantidad_fuentes < 2:
        puntaje -= 10

    return _clamp(puntaje)


def evaluar_producto_multifuente(producto_canonico):
    comparacion = calcular_comparacion_producto(producto_canonico)
    mejor_aparicion = None
    mejor_precio = None
    for producto_fuente in producto_canonico.apariciones.prefetch_related("precios_fuente"):
        ultimo_precio = producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()
        if ultimo_precio and (mejor_precio is None or ultimo_precio.precio < mejor_precio.precio):
            mejor_precio = ultimo_precio
            mejor_aparicion = producto_fuente

    if not mejor_aparicion or not mejor_precio:
        return None

    resultado = calcular_resultado_comercial(mejor_precio.precio, comparacion.precio_promedio or None)
    indice = calcular_indice_oportunidad(producto_canonico, mejor_aparicion)
    tipo = EvaluacionOportunidadMultifuente.TIPO_OBSERVAR
    riesgo = "medio"
    if indice >= 75:
        tipo = EvaluacionOportunidadMultifuente.TIPO_REVENTA
        riesgo = "bajo"
    elif indice < 40:
        tipo = EvaluacionOportunidadMultifuente.TIPO_DESCARTAR
        riesgo = "alto"

    return EvaluacionOportunidadMultifuente.objects.create(
        producto_canonico=producto_canonico,
        producto_fuente_origen=mejor_aparicion,
        precio_compra=mejor_precio.precio,
        precio_promedio_mercado=comparacion.precio_promedio,
        precio_reventa_estimado=resultado["precio_reventa_estimado"],
        margen_estimado=resultado["margen_estimado"],
        porcentaje_margen=resultado["porcentaje_margen"],
        indice_oportunidad=indice,
        tipo=tipo,
        riesgo=riesgo,
        motivo="Evaluacion inicial multifuente basada en comparacion de precios y politica de fuente.",
    )
