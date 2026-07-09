import re
from decimal import Decimal, InvalidOperation


def normalizar_precio_argentino(texto_precio):
    if texto_precio is None:
        return None
    texto = str(texto_precio).strip()
    texto = texto.replace("$", "").replace("ARS", "").replace(" ", "")
    texto = re.sub(r"[^0-9,.\-]", "", texto)
    if not texto:
        return None
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "." in texto:
        partes = texto.split(".")
        if len(partes) > 1 and len(partes[-1]) == 3:
            texto = texto.replace(".", "")
    try:
        return Decimal(texto).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def extraer_tienda_producto(linea):
    texto = (linea or "").strip()
    texto = re.sub(r"^\s*[-*#]+\s*", "", texto)
    patron = r"^(.{2,80}?)\s*(?:—|–|-|:)\s*(.{3,250})$"
    match = re.match(patron, texto)
    if not match:
        return None, None
    tienda = match.group(1).strip(" -*#")
    producto = match.group(2).strip()
    if tienda.lower().startswith((
        "radar de ofertas",
        "oportunidad real",
        "precio actual",
        "comparable",
        "otros comparables",
        "descuento",
        "por que",
        "por qué",
        "chequeo",
        "riesgo",
    )):
        return None, None
    return tienda, producto


def _buscar_linea(texto, claves):
    for linea in (texto or "").splitlines():
        normalizada = linea.strip().lower()
        if any(normalizada.startswith(clave) for clave in claves):
            return linea.strip()
    return ""


def _texto_despues_de_etiqueta(linea):
    if ":" in linea:
        return linea.split(":", 1)[1].strip()
    return linea.strip()


def extraer_precio_actual(texto):
    linea = _buscar_linea(texto, ["precio actual"])
    if not linea:
        return None
    match = re.search(r"\$?\s*[\d.]+(?:,\d{1,2})?", linea)
    return normalizar_precio_argentino(match.group(0)) if match else None


def extraer_comparables(texto):
    comparable_linea = _buscar_linea(texto, ["comparable más bajo", "comparable mas bajo", "comparable principal"])
    otros_linea = _buscar_linea(texto, ["otros comparables"])
    comparables_texto = "\n".join(linea for linea in [comparable_linea, otros_linea] if linea)
    precios = [normalizar_precio_argentino(valor) for valor in re.findall(r"\$?\s*[\d.]+(?:,\d{1,2})?", comparables_texto)]
    precios = [precio for precio in precios if precio]
    tienda = None
    precio_principal = precios[0] if precios else None
    if comparable_linea:
        despues = _texto_despues_de_etiqueta(comparable_linea)
        match_tienda = re.search(r"\ben\s+([^,.;]+)", despues, flags=re.IGNORECASE)
        if match_tienda:
            tienda = match_tienda.group(1).strip()
    return {
        "precio_comparable_minimo": min(precios) if precios else None,
        "precio_comparable_maximo": max(precios) if precios else None,
        "comparable_principal_tienda": tienda,
        "comparable_principal_precio": precio_principal,
        "comparables_texto": comparables_texto or None,
    }


def extraer_descuento(texto):
    linea = _buscar_linea(texto, ["descuento real estimado", "descuento estimado", "descuento"])
    if not linea:
        return None, None
    porcentajes = [normalizar_precio_argentino(valor) for valor in re.findall(r"\d+(?:,\d{1,2})?\s*%", linea)]
    porcentajes = [p for p in porcentajes if p is not None]
    return (max(porcentajes) if porcentajes else None, _texto_despues_de_etiqueta(linea))


def _extraer_bloque(texto, inicio_claves, fin_claves):
    lineas = (texto or "").splitlines()
    capturando = False
    bloque = []
    for linea in lineas:
        normalizada = linea.strip().lower()
        if any(normalizada.startswith(clave) for clave in inicio_claves):
            capturando = True
            bloque.append(_texto_despues_de_etiqueta(linea))
            continue
        if capturando and any(normalizada.startswith(clave) for clave in fin_claves):
            break
        if capturando and linea.strip():
            bloque.append(linea.strip())
    return "\n".join(parte for parte in bloque if parte).strip() or None


def extraer_motivo(texto):
    return _extraer_bloque(texto, ["por qué conviene", "por que conviene", "motivo"], ["chequeo", "riesgo", "precio actual", "comparable"])


def extraer_chequeo_antimarketing(texto):
    return _extraer_bloque(texto, ["chequeo anti-marketing", "chequeo antimarketing"], ["riesgo", "precio actual", "comparable", "por qué", "por que"])


def extraer_urls(texto):
    urls = re.findall(r"https?://[^\s)>\"]+", texto or "")
    return {
        "url_oferta": urls[0] if urls else None,
        "url_comparable": urls[1] if len(urls) > 1 else None,
    }


def _extraer_condicion(texto, claves):
    for linea in (texto or "").splitlines():
        normalizada = linea.lower()
        if any(clave in normalizada for clave in claves):
            return linea.strip()[:250]
    return None


def calcular_score_radar(datos):
    score = 0
    descuento = datos.get("descuento_real_pct_estimado")
    if descuento is not None and descuento >= 20:
        score += 30
    elif descuento is not None and descuento < 20:
        score -= 15
    if datos.get("precio_comparable_minimo"):
        score += 20
    else:
        score -= 10
    if datos.get("precio_actual"):
        score += 15
    else:
        score -= 15
    if datos.get("motivo_conveniencia"):
        score += 10
    if datos.get("chequeo_antimarketing"):
        score += 10
    if datos.get("stock_texto") or datos.get("envio_texto") or datos.get("vendedor_texto"):
        score += 10
    if datos.get("url_oferta"):
        score += 5
    if datos.get("requiere_revision"):
        score -= 5
    return max(0, min(100, score))


def _nivel_desde_score(score):
    if score >= 80:
        return "alta"
    if score >= 60:
        return "media"
    if score >= 40:
        return "baja"
    return "dudosa"


def _decision_desde_datos(datos, score):
    descuento = datos.get("descuento_real_pct_estimado")
    tiene_condicion = bool(datos.get("stock_texto") or datos.get("envio_texto") or datos.get("url_oferta"))
    if score >= 85 and descuento is not None and descuento >= 30 and tiene_condicion:
        return "comprar"
    if score >= 60:
        return "analizar"
    if descuento is not None and descuento < 20:
        return "descartar"
    return "esperar"


def _calcular_descuento(precio_actual, precio_comparable):
    if precio_actual and precio_comparable and precio_comparable > 0:
        return ((precio_comparable - precio_actual) / precio_comparable * Decimal("100")).quantize(Decimal("0.01"))
    return None


def _separar_bloques(texto):
    lineas = (texto or "").splitlines()
    indices = []
    for idx, linea in enumerate(lineas):
        tienda, producto = extraer_tienda_producto(linea)
        if tienda and producto:
            indices.append(idx)
    if not indices:
        return [texto] if texto.strip() else []
    bloques = []
    for pos, inicio in enumerate(indices):
        fin = indices[pos + 1] if pos + 1 < len(indices) else len(lineas)
        encabezado_previo = max(0, inicio - 2)
        bloques.append("\n".join(lineas[encabezado_previo:fin]).strip())
    return bloques


def parsear_texto_radar(texto):
    oportunidades = []
    for bloque in _separar_bloques(texto):
        tienda = producto = None
        for linea in bloque.splitlines():
            tienda, producto = extraer_tienda_producto(linea)
            if tienda and producto:
                break
        producto = producto or "Oportunidad detectada"
        comparables = extraer_comparables(bloque)
        descuento_calculado, descuento_texto = extraer_descuento(bloque)
        precio_actual = extraer_precio_actual(bloque)
        descuento = descuento_calculado or _calcular_descuento(precio_actual, comparables["precio_comparable_minimo"])
        urls = extraer_urls(bloque)
        datos = {
            "tienda": tienda,
            "producto_nombre": producto,
            "titulo": f"{tienda} - {producto}" if tienda else producto,
            "precio_actual": precio_actual,
            "descuento_real_pct_estimado": descuento,
            "descuento_texto": descuento_texto,
            "motivo_conveniencia": extraer_motivo(bloque),
            "chequeo_antimarketing": extraer_chequeo_antimarketing(bloque),
            "envio_texto": _extraer_condicion(bloque, ["envio", "envío", "llegada", "entrega"]),
            "stock_texto": _extraer_condicion(bloque, ["stock"]),
            "vendedor_texto": _extraer_condicion(bloque, ["vendedor"]),
            "riesgo_texto": _extraer_condicion(bloque, ["riesgo"]),
            "texto_original": bloque,
            "advertencias": [],
        }
        datos.update(comparables)
        datos.update(urls)
        if not datos["precio_actual"]:
            datos["advertencias"].append("Sin precio actual")
        if not datos["precio_comparable_minimo"]:
            datos["advertencias"].append("Sin comparable confiable")
        if not datos["url_oferta"]:
            datos["advertencias"].append("Sin URL")
        datos["requiere_revision"] = bool(datos["advertencias"])
        datos["score_radar"] = calcular_score_radar(datos)
        datos["nivel_oportunidad"] = _nivel_desde_score(datos["score_radar"])
        datos["decision_sugerida"] = _decision_desde_datos(datos, datos["score_radar"])
        oportunidades.append(datos)
    return oportunidades
