import csv
import hashlib
import io
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal

from django.db import transaction

from oportunidades.models import CategoriaInteres, FuenteWeb, ItemRanking, LoteRanking, ProductoFuente
from oportunidades.services.categorias_service import clasificar_categoria_producto
from oportunidades.services.normalizacion_supermercado_service import (
    calcular_presentacion,
    inferir_presentacion_desde_texto,
    parsear_precio_normalizado,
)


COLUMNAS = {
    "posicion": {"ranking", "posicion", "puesto", "#"},
    "producto": {"producto", "nombre", "item", "articulo"},
    "categoria": {"categoria", "rubro"},
    "tienda": {"tienda donde aparece fuerte", "tienda", "fuente", "comercio"},
    "senal": {"senal de venta", "senal", "motivo", "observacion"},
    "estado": {"estado", "alerta", "decision", "resultado"},
    "url": {"url", "evidencia", "enlace", "link"},
    "marca": {"marca"},
    "subcategoria": {"subcategoria"},
    "precio": {"precio", "precio total", "precio_final_total"},
    "precio_normalizado": {
        "precio normalizado",
        "precio_normalizado",
        "normalizacion",
        "normalizado",
        "precio por litro",
        "precio litro",
        "precio por kg",
        "precio por metro",
        "precio por unidad",
    },
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9#\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def limpiar_markdown(texto):
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", str(texto or ""))
    texto = re.sub(r"__(.*?)__", r"\1", texto)
    texto = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 \2", texto)
    texto = re.sub(r"\[\d+\]", "", texto)
    return texto.strip()


def extraer_url(texto):
    texto = str(texto or "")
    md = re.search(r"\[[^\]]+\]\((https?://[^)]+)\)", texto)
    if md:
        return md.group(1).strip()
    url = re.search(r"https?://\S+", texto)
    return url.group(0).rstrip(").,") if url else ""


def _mapear_columnas(headers):
    mapa = {}
    for header in headers:
        normalizado = _normalizar(header)
        for campo, aliases in COLUMNAS.items():
            if normalizado in aliases:
                mapa[header] = campo
                break
    return mapa


def _fila_normalizada(row, mapa):
    salida = {campo: "" for campo in COLUMNAS}
    for header, valor in row.items():
        campo = mapa.get(header)
        if campo:
            salida[campo] = extraer_url(valor) if campo == "url" else limpiar_markdown(valor)
    if not salida["url"]:
        salida["url"] = extraer_url(" ".join(str(v or "") for v in row.values()))
    return salida


def parsear_markdown(texto):
    lineas = [linea.strip() for linea in str(texto or "").splitlines() if linea.strip().startswith("|")]
    if len(lineas) < 2:
        return [], ["No se detecto una tabla Markdown valida."]
    headers = [limpiar_markdown(celda) for celda in lineas[0].strip("|").split("|")]
    mapa = _mapear_columnas(headers)
    rows = []
    for linea in lineas[2:]:
        celdas = [celda.strip() for celda in linea.strip("|").split("|")]
        row = {headers[i]: celdas[i] if i < len(celdas) else "" for i in range(len(headers))}
        rows.append(_fila_normalizada(row, mapa))
    return rows, validar_columnas(mapa)


def parsear_csv_texto(texto):
    try:
        reader = csv.DictReader(io.StringIO(str(texto or "")))
        headers = reader.fieldnames or []
        mapa = _mapear_columnas(headers)
        return [_fila_normalizada(row, mapa) for row in reader], validar_columnas(mapa)
    except csv.Error as exc:
        return [], [f"No se pudo leer el CSV: {exc}"]


def parsear_tabla_ranking(texto, formato="auto"):
    formato = formato or "auto"
    if formato == "markdown" or (formato == "auto" and "|" in str(texto or "")):
        rows, errores = parsear_markdown(texto)
        if rows:
            return rows, errores
    return parsear_csv_texto(texto)


def validar_columnas(mapa):
    presentes = set(mapa.values())
    faltantes = [campo for campo in ["posicion", "producto", "tienda"] if campo not in presentes]
    return [f"Falta columna requerida: {campo}." for campo in faltantes]


def hash_importacion(texto, fecha_referencia, origen, alcance):
    base = "|".join([str(fecha_referencia), _normalizar(origen), _normalizar(alcance), re.sub(r"\s+", " ", str(texto or "")).strip()])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _parse_posicion(valor, fallback):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return fallback


def _buscar_fuente(tienda):
    normalizada = _normalizar(tienda)
    for fuente in FuenteWeb.objects.all():
        if _normalizar(fuente.nombre) == normalizada or normalizada in _normalizar(fuente.nombre):
            return fuente
    return None


def _buscar_producto(row, fuente=None):
    url = row.get("url")
    if url:
        producto = ProductoFuente.objects.filter(url_producto=url).select_related("producto_canonico").first()
        if producto:
            return producto, 100, "Coincidencia exacta por URL."
    nombre = _normalizar(row.get("producto"))
    qs = ProductoFuente.objects.select_related("producto_canonico", "fuente_web")
    if fuente:
        qs = qs.filter(fuente_web=fuente)
    mejor = None
    mejor_score = 0
    for producto in qs.order_by("-fecha_actualizacion")[:700]:
        titulo = _normalizar(producto.titulo_original)
        palabras = set(nombre.split())
        candidatas = set(titulo.split())
        if not palabras or not candidatas:
            continue
        score = int(len(palabras & candidatas) / len(palabras | candidatas) * 100)
        if score > mejor_score:
            mejor = producto
            mejor_score = score
    if mejor and mejor_score >= 70:
        return mejor, mejor_score, "Coincidencia probable por nombre y tienda."
    return None, mejor_score, "Sin producto relacionado."


def _tipo_evidencia_desde_url(url):
    if not url:
        return ItemRanking.EVIDENCIA_OTRA, False
    texto = _normalizar(url)
    if texto.endswith("pdf"):
        return ItemRanking.EVIDENCIA_PDF, False
    if "mas-vendidos" in texto or "ranking" in texto:
        return ItemRanking.EVIDENCIA_RANKING_TIENDA, False
    if "listado" in texto or "categoria" in texto or "catalogo" in texto:
        return ItemRanking.EVIDENCIA_CATEGORIA, False
    return ItemRanking.EVIDENCIA_FICHA, True


def _tipo_senal(texto):
    t = _normalizar(texto)
    if "mas vendido" in t:
        return ItemRanking.SENAL_ETIQUETA_MAS_VENDIDO
    if "ranking" in t:
        return ItemRanking.SENAL_RANKING_OFICIAL
    if "destacado" in t:
        return ItemRanking.SENAL_BLOQUE_DESTACADO
    if "busqueda" in t:
        return ItemRanking.SENAL_BUSQUEDA_DESTACADA
    return ItemRanking.SENAL_RADAR_CHATGPT


def _texto_senal_desde_row(row):
    return row.get("senal") or row.get("estado") or row.get("precio_normalizado") or ""


def _calculos_desde_fila(fila):
    presentacion = fila.get("presentacion") or {}
    raw = fila.get("raw", {})
    calculos = calcular_presentacion(
        tipo_presentacion=presentacion.get("tipo_presentacion", "individual"),
        unidades_por_presentacion=presentacion.get("unidades_por_presentacion", 1),
        contenido_neto_por_unidad=presentacion.get("contenido_neto_por_unidad", 0),
        unidad_medida_original=presentacion.get("unidad_medida_original", "unidad"),
        precio_final_total=raw.get("precio") or 0,
    )
    normalizado = parsear_precio_normalizado(raw.get("precio_normalizado"))
    for campo, valor in normalizado.items():
        calculos[campo] = valor
    return calculos


def previsualizar_ranking(texto, fecha_referencia=None, origen="Radar ChatGPT - carga manual", alcance="", formato="auto"):
    fecha_referencia = fecha_referencia or date.today()
    rows, errores_columnas = parsear_tabla_ranking(texto, formato)
    h = hash_importacion(texto, fecha_referencia, origen, alcance)
    duplicado = LoteRanking.objects.filter(hash_importacion=h).first()
    preview = []
    errores = list(errores_columnas)
    for idx, row in enumerate(rows, start=1):
        fila_errores = []
        if not row.get("producto"):
            fila_errores.append("Falta producto.")
        if not row.get("posicion"):
            fila_errores.append("Falta ranking/posicion.")
        fuente = _buscar_fuente(row.get("tienda"))
        producto, confianza, mensaje = _buscar_producto(row, fuente)
        categoria = clasificar_categoria_producto(
            titulo=row.get("producto"),
            categoria_original=row.get("categoria"),
            marca=row.get("marca"),
            fuente=fuente,
        )
        evidencia, ficha_exacta = _tipo_evidencia_desde_url(row.get("url"))
        presentacion = inferir_presentacion_desde_texto(row.get("producto"))
        preview.append(
            {
                "numero": idx,
                "valida": not fila_errores,
                "errores": fila_errores,
                "posicion": _parse_posicion(row.get("posicion"), idx),
                "producto": row.get("producto"),
                "categoria": row.get("categoria"),
                "categoria_id": categoria.id if categoria else None,
                "categoria_nombre": categoria.nombre if categoria else "",
                "subcategoria": row.get("subcategoria") or row.get("categoria"),
                "tienda": row.get("tienda"),
                "fuente_web_id": fuente.id if fuente else None,
                "senal": _texto_senal_desde_row(row),
                "tipo_senal": _tipo_senal(_texto_senal_desde_row(row)),
                "url": row.get("url"),
                "tipo_evidencia": evidencia,
                "evidencia_es_ficha_exacta": ficha_exacta,
                "producto_fuente_id": producto.id if producto else None,
                "producto_canonico_id": producto.producto_canonico_id if producto else None,
                "coincidencia_confianza": confianza,
                "coincidencia_mensaje": mensaje,
                "presentacion": {k: str(v) for k, v in presentacion.items()},
                "raw": row,
            }
        )
        errores.extend(f"Fila {idx}: {error}" for error in fila_errores)
    return {"hash": h, "duplicado": duplicado, "filas": preview, "errores": errores, "total": len(preview)}


def _clave_item(item):
    if item.producto_canonico_id:
        return f"canonico:{item.producto_canonico_id}"
    if item.producto_fuente_id:
        return f"fuente:{item.producto_fuente_id}"
    return f"texto:{_normalizar(item.nombre_original)}|{_normalizar(item.tienda)}"


def comparar_lote(lote):
    anterior = (
        LoteRanking.objects.filter(
            tipo_ranking=lote.tipo_ranking,
            alcance__iexact=lote.alcance or "",
            categoria_id=lote.categoria_id,
            estado=LoteRanking.ESTADO_PUBLICADO,
            fecha_referencia__lt=lote.fecha_referencia,
        )
        .exclude(pk=lote.pk)
        .order_by("-fecha_referencia", "-fecha_importacion")
        .first()
    )
    actuales = list(lote.items.select_related("producto_canonico", "producto_fuente"))
    anteriores = {_clave_item(item): item for item in anterior.items.all()} if anterior else {}
    for item in actuales:
        previo = anteriores.get(_clave_item(item))
        if not previo:
            item.tendencia = ItemRanking.TENDENCIA_NUEVO if anterior else ItemRanking.TENDENCIA_SIN_COMPARACION
            item.posicion_anterior = None
            item.variacion_posiciones = 0
        else:
            item.posicion_anterior = previo.posicion
            item.variacion_posiciones = previo.posicion - item.posicion
            if item.variacion_posiciones > 0:
                item.tendencia = ItemRanking.TENDENCIA_SUBIO
            elif item.variacion_posiciones < 0:
                item.tendencia = ItemRanking.TENDENCIA_BAJO
            else:
                item.tendencia = ItemRanking.TENDENCIA_MANTUVO
        historicos = ItemRanking.objects.filter(lote__tipo_ranking=lote.tipo_ranking, lote__alcance__iexact=lote.alcance or "")
        clave = _clave_item(item)
        apariciones = [h for h in historicos.select_related("producto_canonico", "producto_fuente") if _clave_item(h) == clave]
        fechas = [h.fecha_observacion or h.lote.fecha_referencia for h in apariciones]
        item.apariciones_ultimos_lotes = len(apariciones) or 1
        item.primera_fecha_observada = min(fechas) if fechas else lote.fecha_referencia
        item.ultima_fecha_observada = max(fechas) if fechas else lote.fecha_referencia
        item.save(
            update_fields=[
                "posicion_anterior",
                "variacion_posiciones",
                "tendencia",
                "apariciones_ultimos_lotes",
                "primera_fecha_observada",
                "ultima_fecha_observada",
                "fecha_actualizacion",
            ]
        )
    return lote


@transaction.atomic
def confirmar_importacion_ranking(datos_lote, filas_preview, texto_original, usuario=None, permitir_duplicado=False):
    h = datos_lote["hash_importacion"]
    duplicado = LoteRanking.objects.filter(hash_importacion=h).first()
    if duplicado and not permitir_duplicado:
        raise ValueError("Ya existe un lote importado con la misma tabla, fecha, origen y alcance.")
    categoria = None
    categoria_id = datos_lote.get("categoria_id")
    if categoria_id:
        categoria = CategoriaInteres.objects.filter(pk=categoria_id).first()
    lote = LoteRanking.objects.create(
        nombre=datos_lote["nombre"],
        tipo_ranking=datos_lote["tipo_ranking"],
        alcance=datos_lote.get("alcance") or "",
        categoria=categoria,
        fecha_referencia=datos_lote["fecha_referencia"],
        origen=datos_lote.get("origen") or "Radar ChatGPT - carga manual",
        metodologia=datos_lote.get("metodologia") or "",
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        estado=datos_lote.get("estado") or LoteRanking.ESTADO_BORRADOR,
        hash_importacion=h,
        texto_original=texto_original,
        posible_duplicado=bool(duplicado),
    )
    creados = 0
    for fila in filas_preview:
        if not fila.get("valida", True):
            continue
        categoria = CategoriaInteres.objects.filter(pk=fila.get("categoria_id")).first()
        fuente = FuenteWeb.objects.filter(pk=fila.get("fuente_web_id")).first()
        producto_fuente = ProductoFuente.objects.filter(pk=fila.get("producto_fuente_id")).first()
        producto_canonico = producto_fuente.producto_canonico if producto_fuente else None
        calculos = _calculos_desde_fila(fila)
        ItemRanking.objects.create(
            lote=lote,
            posicion=fila["posicion"],
            nombre_original=fila["producto"],
            producto_fuente=producto_fuente,
            producto_canonico=producto_canonico,
            categoria=categoria,
            subcategoria=fila.get("subcategoria") or "",
            marca=fila.get("raw", {}).get("marca") or "",
            tienda=fila.get("tienda") or "",
            fuente_web=fuente,
            texto_senal=fila.get("senal") or "",
            tipo_senal=fila.get("tipo_senal") or ItemRanking.SENAL_CARGA_MANUAL,
            url_evidencia=fila.get("url") or "",
            tipo_evidencia=fila.get("tipo_evidencia") or ItemRanking.EVIDENCIA_OTRA,
            fecha_observacion=datos_lote["fecha_referencia"],
            estado_verificacion=ItemRanking.VERIFICACION_PENDIENTE,
            evidencia_es_ficha_exacta=fila.get("evidencia_es_ficha_exacta", False),
            coincidencia_confianza=fila.get("coincidencia_confianza") or 0,
            coincidencia_mensaje=fila.get("coincidencia_mensaje") or "",
            raw_data=json.dumps(fila.get("raw", {}), ensure_ascii=True),
            **calculos,
        )
        creados += 1
    lote.cantidad_filas = creados
    lote.save(update_fields=["cantidad_filas", "fecha_actualizacion"])
    comparar_lote(lote)
    return lote


def historico_item(item):
    clave = _clave_item(item)
    historicos = []
    qs = ItemRanking.objects.select_related("lote", "producto_canonico", "producto_fuente").filter(lote__tipo_ranking=item.lote.tipo_ranking)
    for candidato in qs:
        if _clave_item(candidato) == clave:
            historicos.append(candidato)
    return sorted(historicos, key=lambda x: (x.lote.fecha_referencia, x.posicion))


def reparar_precios_normalizados_lote(lote):
    if not lote.texto_original:
        return {"actualizados": 0, "mensaje": "El lote no tiene texto_original para recalcular."}
    preview = previsualizar_ranking(
        lote.texto_original,
        fecha_referencia=lote.fecha_referencia,
        origen=lote.origen,
        alcance=lote.alcance or "",
    )
    filas_por_posicion = {fila["posicion"]: fila for fila in preview["filas"]}
    actualizados = 0
    campos_calculo = [
        "tipo_presentacion",
        "unidades_por_presentacion",
        "contenido_neto_por_unidad",
        "unidad_medida_original",
        "presentaciones_incluidas",
        "unidades_totales",
        "contenido_total",
        "precio_final_total",
        "costo_envio_traslado",
        "costo_final_puesto_salta",
        "precio_por_unidad",
        "precio_por_litro",
        "precio_por_kg",
        "precio_por_metro",
        "precio_por_100",
        "tipo_promocion",
        "cantidad_total_recibida",
        "cantidad_pagada",
        "precio_total_efectivo",
    ]
    for item in lote.items.all():
        fila = filas_por_posicion.get(item.posicion)
        if not fila:
            continue
        calculos = _calculos_desde_fila(fila)
        for campo in campos_calculo:
            setattr(item, campo, calculos[campo])
        if not item.texto_senal and fila.get("senal"):
            item.texto_senal = fila["senal"]
        item.raw_data = json.dumps(fila.get("raw", {}), ensure_ascii=True)
        item.save(update_fields=[*campos_calculo, "texto_senal", "raw_data", "fecha_actualizacion"])
        actualizados += 1
    return {"actualizados": actualizados, "mensaje": "Precios normalizados recalculados."}
