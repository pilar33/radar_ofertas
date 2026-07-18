import csv
import hashlib
import io
import json
import re
import unicodedata
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from oportunidades.models import (
    CategoriaInteres,
    ComercioLocal,
    EvidenciaLocal,
    FuenteWeb,
    LoteCapturaLocal,
    ObjetivoVigilanciaLocal,
    ObservacionPrecioLocal,
    UmbralPrecioLocal,
)
from oportunidades.services.categorias_service import (
    asegurar_categorias_mercaderia_local,
    clasificar_categoria_producto,
)
from oportunidades.services.normalizacion_supermercado_service import D, money


PRECIO_PENDIENTE = {"precio a cargar", "consultar", "sin precio", "pendiente", "s/p", "sp"}

COLUMNAS_LOCALES = {
    "ranking": {"ranking", "puesto", "posicion", "#"},
    "producto": {"producto", "nombre", "item", "articulo"},
    "fuente": {"fuente", "comercio", "lugar", "local", "tienda"},
    "zona": {"zona", "barrio", "ubicacion"},
    "precio": {"precio encontrado", "precio", "precio total", "valor"},
    "presentacion": {"presentacion", "formato", "contenido"},
    "cantidad": {"cantidad", "cantidad envases", "envases"},
    "unidad": {"unidad", "unidad medida"},
    "unidad_normalizada": {"unidad normalizada", "normalizacion", "normalizado"},
    "sirve_para": {"sirve para", "uso", "utilidad"},
    "estado": {"estado", "alerta", "decision"},
    "evidencia": {"evidencia", "url", "foto", "ticket"},
    "observacion": {"observacion", "motivo", "nota"},
    "marca": {"marca"},
    "segunda_marca": {"segunda marca", "segunda_marca"},
    "stock": {"stock", "disponibilidad"},
    "traslado": {"traslado", "envio", "costo traslado", "costo envio"},
}


def _normalizar_texto(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9#/$\s.,]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _limpiar_markdown(texto):
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", str(texto or ""))
    texto = re.sub(r"__(.*?)__", r"\1", texto)
    texto = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 \2", texto)
    return texto.strip()


def _mapear_columnas(headers):
    mapa = {}
    for header in headers:
        normalizado = _normalizar_texto(header).replace("$", "")
        for campo, aliases in COLUMNAS_LOCALES.items():
            if normalizado in aliases:
                mapa[header] = campo
                break
    return mapa


def _fila_normalizada(row, mapa):
    salida = {campo: "" for campo in COLUMNAS_LOCALES}
    for header, valor in row.items():
        campo = mapa.get(header)
        if campo:
            salida[campo] = _limpiar_markdown(valor)
    return salida


def parsear_tabla_local(texto, formato="auto"):
    texto = str(texto or "")
    if formato == "markdown" or (formato == "auto" and "|" in texto):
        lineas = [linea.strip() for linea in texto.splitlines() if linea.strip().startswith("|")]
        if len(lineas) >= 2:
            headers = [_limpiar_markdown(celda) for celda in lineas[0].strip("|").split("|")]
            mapa = _mapear_columnas(headers)
            filas = []
            for linea in lineas[2:]:
                celdas = [celda.strip() for celda in linea.strip("|").split("|")]
                row = {headers[i]: celdas[i] if i < len(celdas) else "" for i in range(len(headers))}
                filas.append(_fila_normalizada(row, mapa))
            return filas, validar_columnas(mapa)
    try:
        reader = csv.DictReader(io.StringIO(texto))
        headers = reader.fieldnames or []
        mapa = _mapear_columnas(headers)
        return [_fila_normalizada(row, mapa) for row in reader], validar_columnas(mapa)
    except csv.Error as exc:
        return [], [f"No se pudo leer el CSV: {exc}"]


def validar_columnas(mapa):
    presentes = set(mapa.values())
    faltantes = [campo for campo in ["producto", "fuente"] if campo not in presentes]
    return [f"Falta columna requerida: {campo}." for campo in faltantes]


def hash_importacion_local(texto, fecha_observacion, zona, metodo):
    base = "|".join([str(fecha_observacion), _normalizar_texto(zona), metodo or "", re.sub(r"\s+", " ", str(texto or "")).strip()])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def precio_pendiente(valor):
    texto = _normalizar_texto(valor)
    return not texto or texto in PRECIO_PENDIENTE or any(p in texto for p in PRECIO_PENDIENTE)


def parsear_precio(valor):
    if precio_pendiente(valor):
        return None
    precio = money(valor)
    if precio <= 0:
        return Decimal("0.00")
    return precio


def _tipo_presentacion(texto):
    t = _normalizar_texto(texto)
    for clave in ["fardo", "bulto", "caja", "bolsa", "pack", "paquete", "botella", "lata", "rollo", "promocion"]:
        if clave in t:
            return clave
    if "kg" in t or "kilo" in t:
        return ObservacionPrecioLocal.TIPO_KILOGRAMO
    return ObservacionPrecioLocal.TIPO_UNIDAD


def _unidad_deseada(unidad_normalizada, presentacion, producto):
    texto = _normalizar_texto(" ".join([unidad_normalizada or "", presentacion or "", producto or ""]))
    if "$/metro" in texto or "/metro" in texto or "/m" in texto or "papel" in texto:
        return UmbralPrecioLocal.UNIDAD_METRO
    if "$/litro" in texto or "/litro" in texto or "/l" in texto or "aceite" in texto or "bebida" in texto or "cerveza" in texto:
        return UmbralPrecioLocal.UNIDAD_LITRO
    if "$/kg" in texto or "/kg" in texto or "kilo" in texto or "fideo" in texto or "arroz" in texto or "harina" in texto or "polenta" in texto or "menudo" in texto:
        return UmbralPrecioLocal.UNIDAD_KG
    return UmbralPrecioLocal.UNIDAD_UNIDAD


def _parse_presentacion(presentacion, cantidad="", unidad_normalizada="", producto=""):
    texto = _normalizar_texto(" ".join([presentacion or "", cantidad or "", unidad_normalizada or "", producto or ""]))
    cantidad_envases = Decimal("1")
    contenido = Decimal("0.000")
    unidad = "unidad"
    metros_por_rollo = Decimal("0.000")
    rollos = Decimal("0")

    match_pack = re.search(r"(?:x|pack de|fardo de|caja de)\s*(\d{1,3})", texto)
    if match_pack:
        cantidad_envases = D(match_pack.group(1), "1")

    match_rollos = re.search(r"(\d{1,3})\s*roll", texto)
    if match_rollos:
        rollos = D(match_rollos.group(1), "0")
        cantidad_envases = rollos
    match_metros = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:m|metro|metros)", texto)
    if match_metros:
        metros_por_rollo = D(match_metros.group(1), "0")
        contenido = metros_por_rollo
        unidad = "metro"

    match_peso_volumen = re.search(r"(\d+(?:[,.]\d+)?)\s*(kg|kilo|kilos|g|gramo|gramos|l|litro|litros|ml)", texto)
    if match_peso_volumen:
        contenido = D(match_peso_volumen.group(1), "0")
        unidad_raw = match_peso_volumen.group(2)
        if unidad_raw in {"g", "gramo", "gramos"}:
            contenido = contenido / Decimal("1000")
            unidad = "kg"
        elif unidad_raw in {"ml"}:
            contenido = contenido / Decimal("1000")
            unidad = "litro"
        elif unidad_raw.startswith("l"):
            unidad = "litro"
        else:
            unidad = "kg"

    unidad_preferida = _unidad_deseada(unidad_normalizada, presentacion, producto)
    if unidad == "unidad" and unidad_preferida == UmbralPrecioLocal.UNIDAD_KG and "1 kg" in texto:
        contenido = Decimal("1.000")
        unidad = "kg"

    if unidad == "metro" and rollos and metros_por_rollo:
        contenido_total = (rollos * metros_por_rollo).quantize(Decimal("0.001"))
    elif contenido:
        contenido_total = (contenido * cantidad_envases).quantize(Decimal("0.001"))
    else:
        contenido_total = Decimal("0.000")

    return {
        "tipo_presentacion": _tipo_presentacion(presentacion),
        "cantidad_envases": cantidad_envases.quantize(Decimal("0.01")),
        "contenido_por_envase": contenido.quantize(Decimal("0.001")),
        "unidad_medida": unidad,
        "unidades_totales": cantidad_envases.quantize(Decimal("0.01")),
        "contenido_total_normalizado": contenido_total,
    }


def calcular_normalizacion_local(precio, presentacion, cantidad="", unidad_normalizada="", producto="", traslado=0):
    datos = _parse_presentacion(presentacion, cantidad, unidad_normalizada, producto)
    precio_total = precio
    costo_traslado = money(traslado or 0)
    if precio_total is None:
        costo_final = Decimal("0.00")
    else:
        costo_final = money(precio_total + costo_traslado)
    unidad_deseada = _unidad_deseada(unidad_normalizada, presentacion, producto)
    precio_por_unidad = money(costo_final / datos["unidades_totales"]) if costo_final and datos["unidades_totales"] else Decimal("0.00")
    precio_por_kg = Decimal("0.00")
    precio_por_litro = Decimal("0.00")
    precio_por_metro = Decimal("0.00")
    if costo_final and datos["contenido_total_normalizado"]:
        if unidad_deseada == UmbralPrecioLocal.UNIDAD_KG or datos["unidad_medida"] == "kg":
            precio_por_kg = money(costo_final / datos["contenido_total_normalizado"])
        elif unidad_deseada == UmbralPrecioLocal.UNIDAD_LITRO or datos["unidad_medida"] == "litro":
            precio_por_litro = money(costo_final / datos["contenido_total_normalizado"])
        elif unidad_deseada == UmbralPrecioLocal.UNIDAD_METRO or datos["unidad_medida"] == "metro":
            precio_por_metro = money(costo_final / datos["contenido_total_normalizado"])
    return {
        **datos,
        "precio_por_unidad": precio_por_unidad,
        "precio_por_kg": precio_por_kg,
        "precio_por_litro": precio_por_litro,
        "precio_por_metro": precio_por_metro,
        "costo_traslado_envio": costo_traslado,
        "costo_final_puesto_salta": costo_final,
        "unidad_preferida": unidad_deseada,
    }


def precio_para_unidad(observacion, unidad):
    if unidad == UmbralPrecioLocal.UNIDAD_KG:
        return observacion.precio_por_kg
    if unidad == UmbralPrecioLocal.UNIDAD_LITRO:
        return observacion.precio_por_litro
    if unidad == UmbralPrecioLocal.UNIDAD_METRO:
        return observacion.precio_por_metro
    return observacion.precio_por_unidad


def buscar_umbral(observacion, fecha=None):
    fecha = fecha or timezone.localdate()
    candidatos = UmbralPrecioLocal.objects.filter(activo=True, fecha_desde__lte=fecha).filter(Q(fecha_hasta__isnull=True) | Q(fecha_hasta__gte=fecha))
    if observacion.zona:
        candidatos = candidatos.filter(Q(zona__isnull=True) | Q(zona="") | Q(zona__iexact=observacion.zona))
    candidatos_validos = []
    candidatos = candidatos.order_by("-producto_canonico_id", "-categoria_id", "-zona", "nombre")
    for umbral in candidatos:
        if umbral.producto_canonico_id and umbral.producto_canonico_id != observacion.producto_canonico_id:
            continue
        if umbral.categoria_id and not _categoria_umbral_compatible(umbral, observacion):
            continue
        if umbral.marca_importa and umbral.marca and _normalizar_texto(umbral.marca) != _normalizar_texto(observacion.marca):
            continue
        if observacion.segunda_marca and not umbral.segunda_marca_aceptada:
            continue
        if precio_para_unidad(observacion, umbral.unidad_normalizada) > 0:
            candidatos_validos.append((_score_umbral(umbral, observacion), umbral))
    if not candidatos_validos:
        return None
    return sorted(candidatos_validos, key=lambda item: item[0], reverse=True)[0][1]


def _categoria_umbral_compatible(umbral, observacion):
    if not observacion.categoria_id:
        return True
    if umbral.categoria_id == observacion.categoria_id:
        return True
    if umbral.categoria and observacion.categoria:
        if umbral.categoria.categoria_padre_id and umbral.categoria.categoria_padre_id == observacion.categoria.categoria_padre_id:
            return True
        if umbral.categoria_id == observacion.categoria.categoria_padre_id:
            return True
        if umbral.categoria.categoria_padre_id == observacion.categoria_id:
            return True
    texto_obs = _normalizar_texto(" ".join([observacion.nombre_original or "", observacion.sirve_para or "", observacion.observaciones or ""]))
    textos_umbral = _normalizar_texto(" ".join([umbral.nombre or "", umbral.grupo_comparable or "", getattr(umbral.categoria, "nombre", "")]))
    tokens = [token for token in textos_umbral.split() if len(token) >= 5]
    return any(token in texto_obs for token in tokens)


def _score_umbral(umbral, observacion):
    score = 0
    texto_obs = _normalizar_texto(" ".join([observacion.nombre_original or "", observacion.sirve_para or "", observacion.observaciones or ""]))
    textos_umbral = _normalizar_texto(" ".join([umbral.nombre or "", umbral.grupo_comparable or "", getattr(umbral.categoria, "nombre", "")]))
    for token in {token for token in textos_umbral.split() if len(token) >= 5}:
        if token in texto_obs:
            score += 10
    if umbral.producto_canonico_id and umbral.producto_canonico_id == observacion.producto_canonico_id:
        score += 100
    if umbral.categoria_id and umbral.categoria_id == observacion.categoria_id:
        score += 20
    if umbral.zona and _normalizar_texto(umbral.zona) == _normalizar_texto(observacion.zona):
        score += 5
    return score


def evaluar_observacion(observacion):
    hoy = timezone.localdate()
    motivos = []
    if observacion.precio_total_encontrado is None:
        observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_VIGILAR
        observacion.clasificacion_final = observacion.clasificacion_manual or observacion.clasificacion_automatica
        observacion.motivo_clasificacion = "Producto interesante sin precio cargado: queda como objetivo de vigilancia."
        observacion.metodo_evaluacion = ObservacionPrecioLocal.METODO_EVALUACION_MANUAL
        return observacion
    if observacion.precio_total_encontrado <= 0:
        observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_DESCARTAR
        motivos.append("Precio invalido o cero.")
    elif observacion.estado_vigencia in {ObservacionPrecioLocal.VIGENCIA_VENCIDA, ObservacionPrecioLocal.VIGENCIA_DESCARTADA}:
        observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_DESCARTAR
        motivos.append("Observacion vencida o descartada.")
    elif observacion.stock_estimado == ObservacionPrecioLocal.STOCK_AGOTADO or observacion.estado_vigencia == ObservacionPrecioLocal.VIGENCIA_AGOTADA:
        observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_DESCARTAR
        motivos.append("Producto agotado.")
    elif observacion.fecha_estimada_fin and observacion.fecha_estimada_fin.date() < hoy:
        observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_DESCARTAR
        motivos.append("Oferta local vencida.")
    elif not any([observacion.precio_por_kg, observacion.precio_por_litro, observacion.precio_por_metro, observacion.precio_por_unidad]):
        observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_REVISAR
        motivos.append("Falta contenido o unidad compatible para normalizar.")
    else:
        umbral = buscar_umbral(observacion, hoy)
        observacion.umbral_aplicado = umbral
        if umbral:
            precio = precio_para_unidad(observacion, umbral.unidad_normalizada)
            observacion.unidad_umbral_aplicada = umbral.unidad_normalizada
            observacion.precio_normalizado_usado = precio
            observacion.diferencia_umbral = money(umbral.precio_maximo_bueno - precio)
            if umbral.precio_maximo_bueno:
                observacion.porcentaje_vs_umbral = D((umbral.precio_maximo_bueno - precio) / umbral.precio_maximo_bueno * Decimal("100")).quantize(Decimal("0.01"))
            if precio <= umbral.precio_maximo_fuerte:
                observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_ALERTA_FUERTE
                motivos.append(f"Precio normalizado {precio} <= umbral fuerte {umbral.precio_maximo_fuerte}.")
            elif precio <= umbral.precio_maximo_bueno:
                observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_BUENA
                motivos.append(f"Precio normalizado {precio} <= umbral bueno {umbral.precio_maximo_bueno}.")
            else:
                observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_DESCARTAR
                motivos.append(f"Precio normalizado {precio} supera umbral bueno {umbral.precio_maximo_bueno}.")
            observacion.metodo_evaluacion = ObservacionPrecioLocal.METODO_PRECIO_UMBRAL
        else:
            observacion.clasificacion_automatica = ObservacionPrecioLocal.CLASIFICACION_REVISAR
            motivos.append("No se encontro umbral vigente compatible.")
    observacion.clasificacion_final = observacion.clasificacion_manual or observacion.clasificacion_automatica
    observacion.motivo_clasificacion = " ".join(motivos)
    return observacion


def obtener_o_crear_comercio(nombre, zona="Salta Capital", tipo_fuente=None):
    nombre = (nombre or "Comercio local sin especificar").strip()
    tipo_fuente = tipo_fuente or FuenteWeb.TIPO_CAPTURA_MANUAL
    comercio, _ = ComercioLocal.objects.get_or_create(
        nombre=nombre,
        zona=zona or "Salta Capital",
        defaults={"tipo_fuente": tipo_fuente, "ciudad": "Salta Capital"},
    )
    return comercio


def _preview_desde_row(row, idx, zona_default):
    precio = parsear_precio(row.get("precio"))
    categoria = clasificar_categoria_producto(row.get("producto"), row.get("unidad_normalizada"), categoria_default=None)
    normalizacion = calcular_normalizacion_local(
        precio,
        row.get("presentacion"),
        cantidad=row.get("cantidad"),
        unidad_normalizada=row.get("unidad_normalizada"),
        producto=row.get("producto"),
        traslado=row.get("traslado") or 0,
    )
    es_objetivo = precio is None
    errores = []
    if precio == Decimal("0.00"):
        errores.append("Precio cero o invalido: no se creara oportunidad activa.")
    if not row.get("producto"):
        errores.append("Falta producto.")
    return {
        "numero": idx,
        "valida": bool(row.get("producto") and row.get("fuente")),
        "errores": errores,
        "ranking": row.get("ranking") or idx,
        "producto": row.get("producto"),
        "fuente": row.get("fuente"),
        "zona": row.get("zona") or zona_default or "Salta Capital",
        "precio": str(precio) if precio is not None else "",
        "precio_pendiente": es_objetivo,
        "presentacion": row.get("presentacion"),
        "unidad_normalizada": row.get("unidad_normalizada"),
        "sirve_para": row.get("sirve_para"),
        "estado": row.get("estado"),
        "evidencia": row.get("evidencia"),
        "observacion": row.get("observacion"),
        "marca": row.get("marca"),
        "segunda_marca": _normalizar_texto(row.get("segunda_marca")) in {"si", "s", "true", "1"},
        "stock": row.get("stock"),
        "categoria_id": categoria.id if categoria else None,
        "categoria_nombre": categoria.nombre if categoria else "",
        "normalizacion": {k: str(v) for k, v in normalizacion.items()},
        "raw": row,
    }


def previsualizar_importacion_local(texto, fecha_observacion=None, zona="Salta Capital", metodo=LoteCapturaLocal.METODO_TABLA_MARKDOWN, formato="auto"):
    asegurar_categorias_mercaderia_local()
    fecha_observacion = fecha_observacion or timezone.now()
    rows, errores_columnas = parsear_tabla_local(texto, formato)
    h = hash_importacion_local(texto, fecha_observacion, zona, metodo)
    duplicado = LoteCapturaLocal.objects.filter(hash_importacion=h).first()
    filas = [_preview_desde_row(row, idx, zona) for idx, row in enumerate(rows, start=1)]
    return {"hash": h, "duplicado": duplicado, "filas": filas, "errores": errores_columnas, "total": len(filas)}


@transaction.atomic
def confirmar_importacion_local(datos_lote, filas_preview, texto_original, usuario=None, permitir_duplicado=False):
    h = datos_lote["hash_importacion"]
    duplicado = LoteCapturaLocal.objects.filter(hash_importacion=h).first()
    if duplicado and not permitir_duplicado:
        raise ValueError("Ya existe un lote local importado con la misma tabla, fecha, zona y metodo.")
    comercio_default = datos_lote.get("comercio")
    lote = LoteCapturaLocal.objects.create(
        nombre=datos_lote["nombre"],
        fecha_observacion=datos_lote["fecha_observacion"],
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        zona=datos_lote.get("zona") or "Salta Capital",
        comercio=comercio_default,
        metodo_captura=datos_lote.get("metodo_captura") or LoteCapturaLocal.METODO_TABLA_MARKDOWN,
        texto_original=texto_original,
        estado=datos_lote.get("estado") or LoteCapturaLocal.ESTADO_BORRADOR,
        observaciones=datos_lote.get("observaciones") or "",
        hash_importacion=h,
        posible_duplicado=bool(duplicado),
    )
    cantidad = 0
    for fila in filas_preview:
        if not fila.get("valida", True):
            continue
        categoria = CategoriaInteres.objects.filter(pk=fila.get("categoria_id")).first()
        comercio = obtener_o_crear_comercio(fila.get("fuente"), fila.get("zona"))
        if fila.get("precio_pendiente"):
            ObjetivoVigilanciaLocal.objects.create(
                lote=lote,
                categoria=categoria,
                nombre_objetivo=fila.get("producto"),
                comercio=comercio,
                zona=fila.get("zona"),
                unidad_deseada=fila.get("unidad_normalizada") or "",
                sirve_para=fila.get("sirve_para") or "",
                motivo="Precio pendiente en importacion local.",
            )
            cantidad += 1
            continue
        normalizacion = fila["normalizacion"]
        observacion = ObservacionPrecioLocal(
            lote=lote,
            categoria=categoria,
            nombre_original=fila.get("producto"),
            marca=fila.get("marca") or "",
            segunda_marca=fila.get("segunda_marca", False),
            comercio=comercio,
            zona=fila.get("zona"),
            fecha_observacion=lote.fecha_observacion,
            precio_total_encontrado=D(fila.get("precio"), "0"),
            tipo_presentacion=normalizacion.get("tipo_presentacion") or ObservacionPrecioLocal.TIPO_UNIDAD,
            cantidad_envases=D(normalizacion.get("cantidad_envases"), "1"),
            contenido_por_envase=D(normalizacion.get("contenido_por_envase"), "0"),
            unidad_medida=normalizacion.get("unidad_medida") or "unidad",
            unidades_totales=D(normalizacion.get("unidades_totales"), "1"),
            contenido_total_normalizado=D(normalizacion.get("contenido_total_normalizado"), "0"),
            precio_por_unidad=D(normalizacion.get("precio_por_unidad"), "0"),
            precio_por_kg=D(normalizacion.get("precio_por_kg"), "0"),
            precio_por_litro=D(normalizacion.get("precio_por_litro"), "0"),
            precio_por_metro=D(normalizacion.get("precio_por_metro"), "0"),
            costo_traslado_envio=D(normalizacion.get("costo_traslado_envio"), "0"),
            costo_final_puesto_salta=D(normalizacion.get("costo_final_puesto_salta"), "0"),
            stock_estimado=fila.get("stock") or ObservacionPrecioLocal.STOCK_DESCONOCIDO,
            estado_vigencia=ObservacionPrecioLocal.VIGENCIA_SIN_CONFIRMAR,
            sirve_para=fila.get("sirve_para") or "",
            observaciones=fila.get("observacion") or "",
            estado_publicacion=lote.estado,
            raw_data=json.dumps(fila.get("raw", {}), ensure_ascii=True),
        )
        evaluar_observacion(observacion)
        observacion.save()
        if fila.get("evidencia"):
            EvidenciaLocal.objects.create(
                observacion=observacion,
                tipo=EvidenciaLocal.TIPO_TEXTO,
                observacion_texto=fila.get("evidencia"),
                nivel_verificacion=EvidenciaLocal.NIVEL_PENDIENTE,
            )
        cantidad += 1
    lote.cantidad_filas = cantidad
    lote.save(update_fields=["cantidad_filas", "fecha_actualizacion"])
    return lote


def ranking_oportunidades_locales(publicas=True):
    qs = ObservacionPrecioLocal.objects.select_related("comercio", "categoria", "umbral_aplicado").prefetch_related("evidencias")
    if publicas:
        qs = qs.filter(estado_publicacion=LoteCapturaLocal.ESTADO_PUBLICADO)
    qs = qs.exclude(clasificacion_final=ObservacionPrecioLocal.CLASIFICACION_DESCARTAR)
    orden = {
        ObservacionPrecioLocal.CLASIFICACION_ALERTA_FUERTE: 1,
        ObservacionPrecioLocal.CLASIFICACION_BUENA: 2,
        ObservacionPrecioLocal.CLASIFICACION_VIGILAR: 3,
        ObservacionPrecioLocal.CLASIFICACION_REVISAR: 4,
    }
    return sorted(qs, key=lambda o: (orden.get(o.clasificacion_final, 9), -o.diferencia_umbral, o.fecha_observacion))
