import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from numbers import Number


Q2 = Decimal("0.01")
Q3 = Decimal("0.001")


def D(valor, default="0"):
    if valor is None or valor == "":
        return Decimal(default)
    if isinstance(valor, Decimal):
        return valor.quantize(Q3)
    if isinstance(valor, Number):
        return Decimal(str(valor)).quantize(Q3)
    texto = str(valor).strip()
    texto = texto.replace("$", "").replace("ARS", "").replace(" ", "")
    texto = re.sub(r"[^0-9,.\-]", "", texto)
    if not texto or texto in {"-", ",", "."}:
        return Decimal(default)
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "." in texto:
        partes = texto.split(".")
        if len(partes) > 2 or (len(partes[-1]) == 3 and all(len(parte) <= 3 for parte in partes[1:])):
            texto = texto.replace(".", "")
    return Decimal(texto).quantize(Q3)


def money(valor):
    return D(valor).quantize(Q2, rounding=ROUND_HALF_UP)


def parsear_precio_normalizado(texto):
    texto_original = str(texto or "").strip()
    if not texto_original:
        return {}
    valor = money(texto_original)
    texto_norm = _normalizar_texto(texto_original)
    if "/l" in texto_norm or " litro" in texto_norm or " por litro" in texto_norm:
        return {"precio_por_litro": valor}
    if "/kg" in texto_norm or " kilo" in texto_norm or " kilogramo" in texto_norm or " por kg" in texto_norm:
        return {"precio_por_kg": valor}
    if "/unidad" in texto_norm or " unidad" in texto_norm or " por unidad" in texto_norm or "/u" in texto_norm:
        return {"precio_por_unidad": valor}
    if "/100" in texto_norm:
        return {"precio_por_100": valor}
    return {"precio_por_unidad": valor}


def _normalizar_texto(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    return re.sub(r"\s+", " ", texto).strip()


def convertir_a_base(cantidad, unidad):
    cantidad = D(cantidad)
    unidad = (unidad or "unidad").lower()
    if unidad == "ml":
        return (cantidad / Decimal("1000")).quantize(Q3), "litro"
    if unidad == "g":
        return (cantidad / Decimal("1000")).quantize(Q3), "kg"
    return cantidad, unidad


def calcular_promocion(tipo_promocion="ninguna", precio_unitario=0, unidades_base=1, descuento_segunda=0, precio_total=None):
    tipo = tipo_promocion or "ninguna"
    precio_unitario = money(precio_unitario)
    unidades_base = D(unidades_base, "1")
    descuento_segunda = D(descuento_segunda)
    if precio_total is not None:
        return {
            "cantidad_total_recibida": unidades_base,
            "cantidad_pagada": unidades_base,
            "precio_total_efectivo": money(precio_total),
        }
    if tipo == "2x1":
        recibida = unidades_base * Decimal("2")
        pagada = unidades_base
    elif tipo == "3x2":
        recibida = unidades_base * Decimal("3")
        pagada = unidades_base * Decimal("2")
    elif tipo == "segunda_descuento":
        recibida = unidades_base * Decimal("2")
        pagada = unidades_base * (Decimal("1") + (Decimal("1") - descuento_segunda / Decimal("100")))
    else:
        recibida = unidades_base
        pagada = unidades_base
    return {
        "cantidad_total_recibida": recibida.quantize(Q2),
        "cantidad_pagada": pagada.quantize(Q2),
        "precio_total_efectivo": money(precio_unitario * pagada),
    }


def calcular_presentacion(
    tipo_presentacion="individual",
    unidades_por_presentacion=1,
    contenido_neto_por_unidad=0,
    unidad_medida_original="unidad",
    presentaciones_incluidas=1,
    precio_final_total=0,
    costo_envio_traslado=0,
    tipo_promocion="ninguna",
    descuento_segunda=0,
):
    unidades_por_presentacion = D(unidades_por_presentacion, "1")
    presentaciones_incluidas = D(presentaciones_incluidas, "1")
    precio_final_total = money(precio_final_total)
    costo_envio_traslado = money(costo_envio_traslado)
    contenido_base, unidad_base = convertir_a_base(contenido_neto_por_unidad, unidad_medida_original)

    unidades_base = unidades_por_presentacion * presentaciones_incluidas
    promo = calcular_promocion(tipo_promocion, precio_total=precio_final_total, unidades_base=unidades_base, descuento_segunda=descuento_segunda)
    unidades_totales = promo["cantidad_total_recibida"] or unidades_base
    costo_final = money(precio_final_total + costo_envio_traslado)
    contenido_total = (contenido_base * unidades_totales).quantize(Q3)

    precio_por_unidad = money(costo_final / unidades_totales) if unidades_totales else Decimal("0.00")
    precio_por_litro = Decimal("0.00")
    precio_por_kg = Decimal("0.00")
    precio_por_100 = Decimal("0.00")
    if unidad_base == "litro" and contenido_total:
        precio_por_litro = money(costo_final / contenido_total)
        precio_por_100 = money(precio_por_litro / Decimal("10"))
    elif unidad_base == "kg" and contenido_total:
        precio_por_kg = money(costo_final / contenido_total)
        precio_por_100 = money(precio_por_kg / Decimal("10"))

    return {
        "tipo_presentacion": tipo_presentacion or "individual",
        "unidades_por_presentacion": unidades_por_presentacion.quantize(Q2),
        "contenido_neto_por_unidad": contenido_base,
        "unidad_medida_original": unidad_base,
        "presentaciones_incluidas": presentaciones_incluidas.quantize(Q2),
        "unidades_totales": unidades_totales.quantize(Q2),
        "contenido_total": contenido_total,
        "precio_final_total": precio_final_total,
        "costo_envio_traslado": costo_envio_traslado,
        "costo_final_puesto_salta": costo_final,
        "precio_por_unidad": precio_por_unidad,
        "precio_por_litro": precio_por_litro,
        "precio_por_kg": precio_por_kg,
        "precio_por_100": precio_por_100,
        "tipo_promocion": tipo_promocion or "ninguna",
        **promo,
    }


def es_oportunidad_bebida(precio_actual_normalizado, precio_referencia_normalizado, umbral=Decimal("20.00")):
    actual = money(precio_actual_normalizado)
    referencia = money(precio_referencia_normalizado)
    if actual <= 0 or referencia <= 0:
        return {"es_oportunidad": False, "descuento": Decimal("0.00")}
    descuento = ((referencia - actual) / referencia * Decimal("100")).quantize(Q2, rounding=ROUND_HALF_UP)
    return {"es_oportunidad": descuento >= umbral, "descuento": descuento}


def inferir_presentacion_desde_texto(texto):
    texto_norm = _normalizar_texto(texto)
    tipo = "individual"
    unidades = Decimal("1")
    if "fardo" in texto_norm:
        tipo = "fardo"
    elif "pack" in texto_norm:
        tipo = "pack"
    elif "bulto" in texto_norm:
        tipo = "bulto"
    match_unidades = re.search(r"(?:x|pack\s*x?)\s*(\d{1,3})", texto_norm)
    if match_unidades:
        unidades = Decimal(match_unidades.group(1))
    match_litros = re.search(r"(\d+(?:[,.]\d+)?)\s*(l|litro|litros|ml)", texto_norm)
    contenido = Decimal("0")
    unidad = "unidad"
    if match_litros:
        contenido = Decimal(match_litros.group(1).replace(",", "."))
        unidad = "litro" if match_litros.group(2).startswith("l") else "ml"
    return {"tipo_presentacion": tipo, "unidades_por_presentacion": unidades, "contenido_neto_por_unidad": contenido, "unidad_medida_original": unidad}
