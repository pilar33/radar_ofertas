from oportunidades.models import ProductoFuente, ResultadoExtraccionWeb
from oportunidades.services.extractor_web_service import detectar_bloqueos_html
from oportunidades.services.normalizacion_service import normalizar_texto_producto


PALABRAS_OFERTA = ["oferta", "descuento", "liquidacion", "liquidación", "promo", "oportunidad", "2x1", "outlet", "sale"]


def _duplicado_probable(resultado):
    fuente = resultado.ejecucion.conector.fuente_web
    if resultado.url_producto and ProductoFuente.objects.filter(fuente_web=fuente, url_producto=resultado.url_producto).exists():
        return True
    titulo = normalizar_texto_producto(resultado.titulo or "")
    return bool(titulo) and any(
        normalizar_texto_producto(producto.titulo_original) == titulo
        for producto in ProductoFuente.objects.filter(fuente_web=fuente)[:200]
    )


def calcular_score_resultado_preview(resultado):
    score = 0
    motivos = []
    texto = " ".join([resultado.titulo or "", resultado.descripcion or "", resultado.mensaje or ""]).lower()
    duplicado = _duplicado_probable(resultado)
    if resultado.precio_decimal and resultado.precio_decimal > 0:
        score += 20
        motivos.append("precio valido")
    else:
        score -= 25
        motivos.append("sin precio")
    if resultado.titulo:
        score += 15
    else:
        score -= 20
    if resultado.url_producto:
        score += 15
    else:
        score -= 10
    if resultado.imagen_url:
        score += 10
    if resultado.descripcion:
        score += 5
    if any(palabra in texto for palabra in PALABRAS_OFERTA):
        score += 15
        motivos.append("palabra de oferta")
    if resultado.procesable:
        score += 10
    if duplicado:
        score -= 30
        motivos.append("duplicado probable")
    if resultado.estado == ResultadoExtraccionWeb.ESTADO_ERROR or detectar_bloqueos_html(texto):
        score -= 40
        motivos.append("error o bloqueo")
    score = max(0, min(100, score))
    resultado.score_preview = score
    resultado.motivo_score = ", ".join(motivos)
    resultado.duplicado_probable = duplicado
    resultado.save(update_fields=["score_preview", "motivo_score", "duplicado_probable"])
    return {"score": score, "motivo": resultado.motivo_score, "duplicado_probable": duplicado}


def rankear_resultados_ejecucion(ejecucion):
    for resultado in ejecucion.resultados_web.all():
        calcular_score_resultado_preview(resultado)
