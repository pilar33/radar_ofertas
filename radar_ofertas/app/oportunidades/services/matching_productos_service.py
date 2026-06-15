import json
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from oportunidades.models import (
    CategoriaInteres,
    OperacionCuraduria,
    ProductoCanonico,
    ProductoFuente,
    SugerenciaMatchingProducto,
)
from oportunidades.services.comparacion_service import calcular_comparacion_producto_canonico
from oportunidades.services.evaluacion_multifuente_service import evaluar_producto_multifuente
from oportunidades.services.ranking_comercial_service import calcular_score_comercial_producto_fuente


PALABRAS_COMERCIALES = {"oferta", "promo", "promocion", "nuevo", "nueva", "novedad", "unidad", "unidades", "tienda", "online"}
PALABRAS_VACIAS = {"de", "del", "la", "las", "el", "los", "con", "para", "por", "y"}
MATERIALES = ("vidrio", "bambu", "madera", "acero", "plastico", "ceramica")
COLORES = ("blanco", "negro", "marron", "cream", "beige", "gris", "rojo", "azul", "verde")


def normalizar_texto_matching(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "").lower()).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"(?<=\d)\s*(mililitros?|ml|cc)\b", "ml", texto)
    texto = re.sub(r"(?<=\d)\s*(litros?|lts?|lt)\b", "l", texto)
    texto = re.sub(r"(?<=\d)\s*(centimetros?|cms?)\b", "cm", texto)
    texto = re.sub(r"(?<=\d)\s*(milimetros?|mms?)\b", "mm", texto)
    texto = re.sub(r"(?<=[a-z])-(?=\d)|(?<=\d)-(?=[a-z])", "", texto)
    texto = re.sub(r"\b(?:unidades?|uds?)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    palabras = [palabra for palabra in texto.split() if palabra not in PALABRAS_COMERCIALES]
    return " ".join(palabras)


def extraer_tokens_producto(texto):
    normalizado = normalizar_texto_matching(texto)
    tokens = []
    for token in normalizado.split():
        if (len(token) > 1 or token.isdigit()) and token not in PALABRAS_VACIAS:
            tokens.append(token)
    return list(dict.fromkeys(tokens))


def extraer_atributos_basicos(texto):
    original = str(texto or "")
    normalizado = normalizar_texto_matching(original)
    cantidad = re.search(
        r"\b(?:set|pack)\s*(?:de\s*)?x?\s*(\d{1,3})\b|\bx(\d{1,3})\b|\b(\d{1,3})\s+(?:frascos?|piezas?|vasos?|platos?|contenedores?)\b",
        normalizado,
    )
    capacidad = re.search(r"\b(\d+(?:[.,]\d+)?\s*(?:ml|cc|l))\b", normalizado)
    medidas = re.search(r"\b(\d+(?:[.,]\d+)?\s*x\s*\d+(?:[.,]\d+)?(?:\s*x\s*\d+(?:[.,]\d+)?)?(?:\s*(?:cm|mm))?|\d+(?:[.,]\d+)?\s*(?:cm|mm))\b", normalizado)
    material = next((valor for valor in MATERIALES if re.search(rf"\b{valor}\b", normalizado)), "")
    color = next((valor for valor in COLORES if re.search(rf"\b{valor}\b", normalizado)), "")
    codigos = re.findall(r"\b(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z]{1,8}[- ]?\d{2,}[a-z0-9-]*\b", original.lower())
    codigo = re.sub(r"[^a-z0-9]", "", codigos[0]) if codigos else ""
    return {
        "cantidad": next((grupo for grupo in cantidad.groups() if grupo), "") if cantidad else "",
        "material": material,
        "capacidad": re.sub(r"\s+", "", capacidad.group(1)) if capacidad else "",
        "medidas": re.sub(r"\s+", "", medidas.group(1)) if medidas else "",
        "color": color,
        "codigo_modelo": codigo,
    }


def _titulo(producto):
    return getattr(producto, "titulo_original", None) or getattr(producto, "nombre_normalizado", "")


def _ultimo_precio_oportunidad(producto):
    precio = producto.precios_fuente.order_by("-fecha_relevamiento", "-id").first()
    if not precio:
        return Decimal("0")
    return precio.precio_oportunidad or precio.precio or Decimal("0")


def calcular_score_similitud_producto(producto_a, producto_b):
    def tokens_comparables(producto):
        resultado = set()
        for token in extraer_tokens_producto(_titulo(producto)):
            token = token[1:] if re.fullmatch(r"x\d+", token) else token
            if len(token) > 4 and token.endswith("s"):
                token = token[:-1]
            resultado.add(token)
        return resultado

    tokens_a = tokens_comparables(producto_a)
    tokens_b = tokens_comparables(producto_b)
    comunes = tokens_a & tokens_b
    union = tokens_a | tokens_b
    proporcion = len(comunes) / len(union) if union else 0
    cobertura = len(comunes) / min(len(tokens_a), len(tokens_b)) if tokens_a and tokens_b else 0
    score = int(proporcion * 15 + cobertura * 55)
    motivos = [f"{len(comunes)} tokens comunes: {', '.join(sorted(comunes)) or 'ninguno'}." ]
    if len(comunes) < 2:
        score -= 12
        motivos.append("Muy pocos tokens relevantes compartidos.")
    elif len(comunes) >= 3:
        score += 5

    atributos_a = extraer_atributos_basicos(_titulo(producto_a))
    atributos_b = extraer_atributos_basicos(_titulo(producto_b))
    pesos = {"cantidad": 12, "material": 10, "capacidad": 10, "medidas": 10, "color": 4, "codigo_modelo": 35}
    for atributo, peso in pesos.items():
        valor_a, valor_b = atributos_a[atributo], atributos_b[atributo]
        if valor_a and valor_b:
            if valor_a == valor_b:
                score += peso
                motivos.append(f"Coincide {atributo}: {valor_a}.")
            elif atributo in {"cantidad", "capacidad", "medidas", "codigo_modelo"}:
                score -= max(5, peso // 2)
                motivos.append(f"Difiere {atributo}: {valor_a} / {valor_b}.")

    canonico_a = getattr(producto_a, "producto_canonico", None)
    canonico_b = getattr(producto_b, "producto_canonico", None)
    categoria_a = canonico_a.categoria_id if canonico_a else getattr(getattr(producto_a, "categoria_fuente", None), "categoria_normalizada_id", None)
    categoria_b = canonico_b.categoria_id if canonico_b else getattr(getattr(producto_b, "categoria_fuente", None), "categoria_normalizada_id", None)
    if canonico_a and canonico_b and canonico_a.pk == canonico_b.pk:
        score += 15
        motivos.append("Ya comparten ProductoCanonico.")
    elif categoria_a and categoria_b:
        if categoria_a == categoria_b:
            score += 8
            motivos.append("Misma categoria normalizada.")
        else:
            score -= 18
            motivos.append("Categorias normalizadas distintas.")

    if producto_a.fuente_web_id != producto_b.fuente_web_id:
        score += 5
        motivos.append("Productos de fuentes distintas.")
    else:
        score -= 5
        motivos.append("Misma fuente: posible duplicado interno.")

    precio_a, precio_b = _ultimo_precio_oportunidad(producto_a), _ultimo_precio_oportunidad(producto_b)
    if precio_a > 0 and precio_b > 0:
        relacion = max(precio_a, precio_b) / min(precio_a, precio_b)
        if relacion >= 4:
            score -= 10
            motivos.append("Diferencia de precio extrema.")

    score = max(0, min(100, score))
    nivel = "alto" if score >= 80 else "medio" if score >= 60 else "bajo" if score >= 40 else "descartar"
    return {
        "score": score,
        "nivel": nivel,
        "motivos": motivos,
        "tokens_comunes": sorted(comunes),
        "atributos_a": atributos_a,
        "atributos_b": atributos_b,
    }


def generar_sugerencias_matching(fuente_id=None, solo_pendientes=True, limite=500, min_score=60, incluir_misma_fuente=False, forzar=False):
    productos = ProductoFuente.objects.select_related(
        "fuente_web", "producto_canonico__categoria", "categoria_fuente__categoria_normalizada"
    ).prefetch_related("precios_fuente").filter(descartado_curaduria=False)
    if fuente_id:
        productos = productos.filter(Q(fuente_web_id=fuente_id) | Q(fuente_web_id__isnull=False))
    productos = list(productos.order_by("-fecha_actualizacion")[: max(int(limite), 2)])
    indice = defaultdict(set)
    for producto in productos:
        for token in extraer_tokens_producto(producto.titulo_original):
            if len(token) >= 3 or any(char.isdigit() for char in token):
                indice[token].add(producto.pk)
    por_id = {producto.pk: producto for producto in productos}
    pares = set()
    for ids in indice.values():
        ids = sorted(ids)
        for posicion, producto_a_id in enumerate(ids):
            for producto_b_id in ids[posicion + 1 : posicion + 26]:
                pares.add((producto_a_id, producto_b_id))

    resumen = {"productos_evaluados": len(productos), "comparaciones": 0, "creadas": 0, "omitidas": 0, "duplicadas": 0, "errores": 0}
    for producto_a_id, producto_b_id in sorted(pares)[: int(limite)]:
        producto_a, producto_b = por_id[producto_a_id], por_id[producto_b_id]
        if fuente_id and producto_a.fuente_web_id != int(fuente_id) and producto_b.fuente_web_id != int(fuente_id):
            continue
        if not incluir_misma_fuente and producto_a.fuente_web_id == producto_b.fuente_web_id:
            resumen["omitidas"] += 1
            continue
        if producto_a.producto_canonico_id and producto_a.producto_canonico_id == producto_b.producto_canonico_id:
            resumen["omitidas"] += 1
            continue
        resumen["comparaciones"] += 1
        resultado = calcular_score_similitud_producto(producto_a, producto_b)
        if resultado["score"] < int(min_score):
            resumen["omitidas"] += 1
            continue
        existente = SugerenciaMatchingProducto.objects.filter(producto_a_id=producto_a_id, producto_b_id=producto_b_id).first()
        if existente:
            if existente.estado == SugerenciaMatchingProducto.ESTADO_RECHAZADA and not forzar:
                resumen["omitidas"] += 1
            else:
                resumen["duplicadas"] += 1
            continue
        sugerido = producto_a.producto_canonico or producto_b.producto_canonico
        SugerenciaMatchingProducto.objects.create(
            producto_a=producto_a,
            producto_b=producto_b,
            score=resultado["score"],
            nivel=resultado["nivel"],
            motivos=json.dumps(resultado["motivos"], ensure_ascii=False),
            producto_canonico_sugerido=sugerido,
        )
        resumen["creadas"] += 1
    return resumen


def _categoria_para_productos(producto_a, producto_b):
    for producto in (producto_a, producto_b):
        if producto.producto_canonico_id:
            return producto.producto_canonico.categoria
        if producto.categoria_fuente_id and producto.categoria_fuente.categoria_normalizada_id:
            return producto.categoria_fuente.categoria_normalizada
    return CategoriaInteres.objects.filter(activa=True).order_by("prioridad", "id").first() or CategoriaInteres.objects.first()


@transaction.atomic
def aceptar_sugerencia_matching(sugerencia, producto_canonico_destino=None, nota_revision=""):
    producto_a, producto_b = sugerencia.producto_a, sugerencia.producto_b
    if producto_canonico_destino:
        destino = producto_canonico_destino
    elif producto_a.producto_canonico_id and not producto_b.producto_canonico_id:
        destino = producto_a.producto_canonico
    elif producto_b.producto_canonico_id and not producto_a.producto_canonico_id:
        destino = producto_b.producto_canonico
    elif producto_a.producto_canonico_id and producto_a.producto_canonico_id == producto_b.producto_canonico_id:
        destino = producto_a.producto_canonico
    elif producto_a.producto_canonico_id and producto_b.producto_canonico_id:
        raise ValueError("Los productos pertenecen a canonicos distintos; seleccione un destino.")
    else:
        categoria = _categoria_para_productos(producto_a, producto_b)
        if not categoria:
            raise ValueError("No hay una CategoriaInteres disponible para crear el ProductoCanonico.")
        titulo = max((producto_a.titulo_original, producto_b.titulo_original), key=len)
        atributos = extraer_atributos_basicos(titulo)
        destino = ProductoCanonico.objects.create(
            nombre_normalizado=normalizar_texto_matching(titulo),
            categoria=categoria,
            modelo=atributos["codigo_modelo"] or None,
            atributos_clave=json.dumps(atributos, ensure_ascii=False),
        )

    for producto in (producto_a, producto_b):
        anterior = producto.producto_canonico_id
        producto.producto_canonico = destino
        producto.requiere_revision = False
        producto.save(update_fields=["producto_canonico", "requiere_revision", "fecha_actualizacion"])
        OperacionCuraduria.objects.create(
            tipo_operacion=OperacionCuraduria.TIPO_REASIGNAR,
            producto_fuente=producto,
            producto_canonico=destino,
            descripcion=f"Matching aceptado desde sugerencia #{sugerencia.pk}.",
            datos_antes=str(anterior or ""),
            datos_despues=str(destino.pk),
        )
    sugerencia.estado = SugerenciaMatchingProducto.ESTADO_ACEPTADA
    sugerencia.producto_canonico_sugerido = destino
    sugerencia.fecha_revision = timezone.now()
    sugerencia.nota_revision = nota_revision
    sugerencia.save(update_fields=["estado", "producto_canonico_sugerido", "fecha_revision", "nota_revision"])
    calcular_comparacion_producto_canonico(destino)
    evaluar_producto_multifuente(destino)
    calcular_score_comercial_producto_fuente(producto_a)
    calcular_score_comercial_producto_fuente(producto_b)
    return destino


def revisar_sugerencia_matching(sugerencia, estado, nota_revision=""):
    if estado not in {SugerenciaMatchingProducto.ESTADO_RECHAZADA, SugerenciaMatchingProducto.ESTADO_IGNORADA}:
        raise ValueError("Estado de revision invalido.")
    sugerencia.estado = estado
    sugerencia.fecha_revision = timezone.now()
    sugerencia.nota_revision = nota_revision
    sugerencia.save(update_fields=["estado", "fecha_revision", "nota_revision"])
    return sugerencia
