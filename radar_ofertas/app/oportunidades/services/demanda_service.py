import re
import unicodedata
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup
from django.db.models import Q
from django.utils import timezone

from oportunidades.models import ProductoFuente, ResultadoExtraccionWeb, ResultadoLaboratorioMapeo, SenalDemandaProducto


def _normalizar(texto):
    return "".join(
        caracter for caracter in unicodedata.normalize("NFKD", str(texto or "").lower()) if not unicodedata.combining(caracter)
    )


def _entero_match(patron, texto):
    match = re.search(patron, texto, flags=re.IGNORECASE)
    if not match:
        return 0, ""
    valor = re.sub(r"[^0-9]", "", match.group(1))
    return (int(valor) if valor else 0), match.group(0)[:200]


def extraer_senales_demanda_desde_texto(texto):
    original = re.sub(r"\s+", " ", str(texto or "")).strip()
    normalizado = _normalizar(original)
    vendidos, texto_vendidos = _entero_match(r"\+?\s*([0-9][0-9. ]*)\s+vendid[oa]s?", normalizado)
    resenas, _ = _entero_match(r"([0-9][0-9. ]*)\s+(?:opiniones|resenas|valoraciones)", normalizado)
    preguntas, _ = _entero_match(r"([0-9][0-9. ]*)\s+preguntas?", normalizado)
    stock, texto_stock = _entero_match(r"(?:quedan?|stock(?:\s+disponible)?)[\s:]*(\d+)", normalizado)
    agotado = bool(re.search(r"\b(?:sin stock|agotad[oa])\b", normalizado))
    ultimas = bool(re.search(r"\bultimas? unidades?\b", normalizado))
    if agotado:
        texto_stock = "Sin stock / agotado"
        stock = 0
    elif ultimas and not texto_stock:
        texto_stock = "Ultimas unidades"
    elif "stock disponible" in normalizado and not texto_stock:
        texto_stock = "Stock disponible (cantidad no informada)"

    calificacion = Decimal("0.00")
    match_calificacion = re.search(r"(?:calificacion|rating)?\s*\b([1-5](?:[.,]\d{1,2}))\b\s*(?:/\s*5|estrellas?)?", normalizado)
    if match_calificacion:
        try:
            calificacion = Decimal(match_calificacion.group(1).replace(",", ".")).quantize(Decimal("0.01"))
        except InvalidOperation:
            calificacion = Decimal("0.00")

    mas_vendido = bool(re.search(r"\b(?:mas vendido|top ventas?)\b", normalizado))
    destacado = "destacado" in normalizado or "mas buscado" in normalizado
    tendencia = "tendencia" in normalizado
    observaciones = []
    if agotado:
        observaciones.append("Producto agotado segun texto visible.")
    if ultimas:
        observaciones.append("Ultimas unidades es una senal de stock, no una venta confirmada.")
    resultado = {
        "cantidad_vendida_visible": vendidos,
        "texto_vendidos": texto_vendidos,
        "cantidad_resenas": resenas,
        "cantidad_preguntas": preguntas,
        "calificacion": calificacion,
        "etiqueta_mas_vendido": mas_vendido,
        "etiqueta_destacado": destacado,
        "etiqueta_tendencia": tendencia,
        "stock_visible": stock,
        "texto_stock": texto_stock,
        "observaciones": " ".join(observaciones),
    }
    resultado["texto_demanda_detectado"] = original[:1500] if any(
        resultado.get(campo)
        for campo in (
            "cantidad_vendida_visible", "cantidad_resenas", "cantidad_preguntas", "calificacion",
            "etiqueta_mas_vendido", "etiqueta_destacado", "etiqueta_tendencia", "texto_stock",
        )
    ) else ""
    return resultado


def extraer_senales_demanda_desde_card(card):
    if hasattr(card, "get_text"):
        texto = card.get_text(" ", strip=True)
        badges = " ".join(
            elemento.get_text(" ", strip=True)
            for elemento in card.select(".badge, .label, [class*='badge'], [class*='tag'], [class*='stock']")
        )
        texto = f"{texto} {badges}".strip()
    else:
        texto = BeautifulSoup(str(card or ""), "lxml").get_text(" ", strip=True)
    datos = extraer_senales_demanda_desde_texto(texto)
    datos["texto_demanda_detectado"] = texto[:1500] if any(
        datos.get(campo)
        for campo in (
            "cantidad_vendida_visible",
            "cantidad_resenas",
            "cantidad_preguntas",
            "calificacion",
            "etiqueta_mas_vendido",
            "etiqueta_destacado",
            "etiqueta_tendencia",
            "texto_stock",
        )
    ) else ""
    return datos


def calcular_score_demanda(senales):
    score = 0
    motivos = []
    vendidos = int(senales.get("cantidad_vendida_visible") or 0)
    resenas = int(senales.get("cantidad_resenas") or 0)
    preguntas = int(senales.get("cantidad_preguntas") or 0)
    calificacion = Decimal(senales.get("calificacion") or 0)
    if vendidos:
        score += min(45, 20 + vendidos // 5)
        motivos.append(f"{vendidos} vendidos visibles informados por la fuente.")
    if resenas:
        score += min(30, 8 + resenas // 10)
        motivos.append(f"{resenas} resenas/opiniones.")
    if preguntas:
        score += min(10, 3 + preguntas // 10)
        motivos.append(f"{preguntas} preguntas.")
    if calificacion >= Decimal("4.5"):
        score += 10
        motivos.append(f"Calificacion {calificacion}.")
    if senales.get("etiqueta_mas_vendido"):
        score += 20
        motivos.append("Etiqueta mas vendido/top ventas.")
    if senales.get("etiqueta_destacado") or senales.get("aparece_en_destacados"):
        score += 40
        motivos.append("Producto destacado.")
    if senales.get("etiqueta_tendencia"):
        score += 12
        motivos.append("Etiqueta tendencia.")
    if senales.get("aparece_en_promociones"):
        score += 5
        motivos.append("Aparece en promociones.")
    if senales.get("aparece_en_varias_fuentes"):
        score += min(15, 5 * int(senales.get("cantidad_fuentes_donde_aparece") or 2))
        motivos.append(f"Aparece en {senales.get('cantidad_fuentes_donde_aparece', 2)} fuentes.")
    recurrencia = int(senales.get("recurrencia_en_previews") or 0)
    if recurrencia > 1:
        score += min(12, recurrencia * 2)
        motivos.append(f"Detectado {recurrencia} veces en previews.")
    variacion = int(senales.get("variacion_stock") or 0)
    if variacion < 0:
        score += min(10, abs(variacion))
        motivos.append("Caida de stock: indicio, no venta confirmada.")
    texto_stock = _normalizar(senales.get("texto_stock"))
    agotado = "sin stock" in texto_stock or "agotado" in texto_stock
    if agotado:
        score -= 20
        motivos.append("Producto agotado o sin stock.")
    elif int(senales.get("stock_visible") or 0) > 0 or "stock disponible" in texto_stock:
        score += 4
        motivos.append("Stock visible disponible.")
    if senales.get("requiere_revision"):
        score -= 15
        motivos.append("Senal marcada para revision.")
    score = max(0, min(100, score))
    hay_senales = bool(motivos)
    nivel = (
        ProductoFuente.DEMANDA_ALTA if score >= 70 else
        ProductoFuente.DEMANDA_MEDIA if score >= 40 else
        ProductoFuente.DEMANDA_BAJA if hay_senales else
        ProductoFuente.DEMANDA_DESCONOCIDA
    )
    motivo = " ".join(motivos) if motivos else "Demanda desconocida; no hay senales visibles suficientes."
    return {"score": score, "nivel": nivel, "motivo": motivo}


def _recurrencia_preview(producto_fuente):
    consulta = Q()
    if producto_fuente.url_producto:
        consulta |= Q(url_producto=producto_fuente.url_producto)
    if producto_fuente.titulo_original:
        consulta |= Q(titulo__iexact=producto_fuente.titulo_original)
    if not consulta:
        return 0
    return ResultadoExtraccionWeb.objects.filter(consulta).count() + ResultadoLaboratorioMapeo.objects.filter(consulta).count()


def crear_o_actualizar_senal_demanda(producto_fuente, datos, origen_dato=None):
    datos = dict(datos or {})
    anterior = producto_fuente.senales_demanda.order_by("-fecha_relevamiento", "-id").first()
    stock_anterior = anterior.stock_visible if anterior else 0
    stock_visible = int(datos.get("stock_visible") or 0)
    datos.setdefault("stock_anterior", stock_anterior)
    datos.setdefault("variacion_stock", stock_visible - stock_anterior if anterior and stock_visible else 0)
    datos.setdefault("recurrencia_en_previews", _recurrencia_preview(producto_fuente))
    if producto_fuente.producto_canonico_id:
        cantidad_fuentes = producto_fuente.producto_canonico.apariciones.values("fuente_web_id").distinct().count()
    else:
        cantidad_fuentes = 1
    datos.setdefault("cantidad_fuentes_donde_aparece", cantidad_fuentes)
    datos.setdefault("aparece_en_varias_fuentes", cantidad_fuentes >= 2)
    calculo = calcular_score_demanda(datos)
    campos_modelo = {campo.name for campo in SenalDemandaProducto._meta.fields}
    valores = {clave: valor for clave, valor in datos.items() if clave in campos_modelo and clave not in {"id", "producto_fuente", "fuente_web", "fecha_relevamiento"}}
    valores.update(
        {
            "score_demanda": calculo["score"],
            "nivel_demanda": calculo["nivel"],
            "motivo_demanda": calculo["motivo"],
            "origen_dato": origen_dato or datos.get("origen_dato") or (SenalDemandaProducto.ORIGEN_DIRECTO if datos.get("cantidad_vendida_visible") else SenalDemandaProducto.ORIGEN_ESTIMADO),
        }
    )
    senal = SenalDemandaProducto.objects.create(
        producto_fuente=producto_fuente,
        fuente_web=producto_fuente.fuente_web,
        **valores,
    )
    producto_fuente.score_demanda_actual = senal.score_demanda
    producto_fuente.nivel_demanda_actual = senal.nivel_demanda
    producto_fuente.motivo_demanda_actual = senal.motivo_demanda
    producto_fuente.fecha_demanda_actual = timezone.now()
    producto_fuente.save(update_fields=["score_demanda_actual", "nivel_demanda_actual", "motivo_demanda_actual", "fecha_demanda_actual", "fecha_actualizacion"])
    return senal


def recalcular_demanda_producto(producto_fuente):
    anterior = producto_fuente.senales_demanda.order_by("-fecha_relevamiento", "-id").first()
    datos = {}
    if anterior:
        for campo in SenalDemandaProducto._meta.fields:
            if campo.name not in {"id", "producto_fuente", "fuente_web", "fecha_relevamiento", "score_demanda", "nivel_demanda", "motivo_demanda", "origen_dato"}:
                datos[campo.name] = getattr(anterior, campo.name)
    datos["recurrencia_en_previews"] = _recurrencia_preview(producto_fuente)
    return crear_o_actualizar_senal_demanda(producto_fuente, datos, SenalDemandaProducto.ORIGEN_CALCULADO)


def actualizar_demanda_por_fuentes(producto_canonico):
    productos = list(producto_canonico.apariciones.select_related("fuente_web"))
    cantidad_fuentes = len({producto.fuente_web_id for producto in productos})
    for producto in productos:
        anterior = producto.senales_demanda.order_by("-fecha_relevamiento", "-id").first()
        datos = {}
        if anterior:
            datos = {campo.name: getattr(anterior, campo.name) for campo in SenalDemandaProducto._meta.fields if campo.name not in {"id", "producto_fuente", "fuente_web", "fecha_relevamiento", "score_demanda", "nivel_demanda", "motivo_demanda", "origen_dato"}}
        datos.update({"cantidad_fuentes_donde_aparece": cantidad_fuentes, "aparece_en_varias_fuentes": cantidad_fuentes >= 2})
        crear_o_actualizar_senal_demanda(producto, datos, SenalDemandaProducto.ORIGEN_CALCULADO)
    return cantidad_fuentes
