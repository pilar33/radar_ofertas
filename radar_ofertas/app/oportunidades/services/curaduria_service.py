import json
import re
import unicodedata
from difflib import SequenceMatcher

from django.db import transaction
from django.utils import timezone

from oportunidades.models import OperacionCuraduria, PrecioFuente, ProductoCanonico, ProductoFuente, ResultadoExtraccionWeb
from oportunidades.services.comparacion_service import calcular_comparacion_producto
from oportunidades.services.evaluacion_multifuente_service import evaluar_producto_multifuente


def normalizar_titulo_para_dedupe(titulo):
    texto = "".join(c for c in unicodedata.normalize("NFKD", str(titulo or "")) if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    palabras_comunes = {"set", "pack", "x", "de", "del", "la", "el", "con", "para"}
    palabras = [p for p in texto.split() if p not in palabras_comunes]
    return " ".join(palabras)


def calcular_score_duplicado(producto_a, producto_b):
    if producto_a.pk == producto_b.pk:
        return 0
    score = 0
    if producto_a.fuente_web_id == producto_b.fuente_web_id:
        score += 20
    if producto_a.url_producto and producto_a.url_producto == producto_b.url_producto:
        score += 60
    if producto_a.codigo_externo and producto_a.codigo_externo == producto_b.codigo_externo:
        score += 50
    if producto_a.imagen_url and producto_a.imagen_url == producto_b.imagen_url:
        score += 20
    similitud = SequenceMatcher(
        None,
        normalizar_titulo_para_dedupe(producto_a.titulo_original),
        normalizar_titulo_para_dedupe(producto_b.titulo_original),
    ).ratio()
    score += int(similitud * 40)
    if producto_a.producto_canonico_id and producto_a.producto_canonico_id == producto_b.producto_canonico_id:
        score += 20
    return min(score, 100)


def detectar_producto_fuente_duplicados(producto_fuente, minimo_score=70):
    candidatos = ProductoFuente.objects.exclude(pk=producto_fuente.pk).filter(fuente_web=producto_fuente.fuente_web)
    duplicados = []
    for candidato in candidatos[:500]:
        score = calcular_score_duplicado(producto_fuente, candidato)
        if score >= minimo_score:
            duplicados.append({"producto": candidato, "score": score})
    return sorted(duplicados, key=lambda item: item["score"], reverse=True)


def detectar_duplicados_globales(fuente_id=None, minimo_score=80):
    qs = ProductoFuente.objects.select_related("fuente_web", "producto_canonico")
    if fuente_id:
        qs = qs.filter(fuente_web_id=fuente_id)
    productos = list(qs[:1000])
    pares = []
    for index, producto in enumerate(productos):
        for candidato in productos[index + 1 :]:
            score = calcular_score_duplicado(producto, candidato)
            if score >= minimo_score:
                pares.append((producto, candidato, score))
    return pares


def marcar_requiere_revision(producto_fuente, motivo):
    motivo_actual = producto_fuente.motivo_revision or ""
    producto_fuente.requiere_revision = True
    producto_fuente.motivo_revision = f"{motivo_actual} {motivo}".strip()
    producto_fuente.save(update_fields=["requiere_revision", "motivo_revision", "fecha_actualizacion"])
    OperacionCuraduria.objects.create(
        tipo_operacion=OperacionCuraduria.TIPO_REVISAR,
        producto_fuente=producto_fuente,
        producto_canonico=producto_fuente.producto_canonico,
        descripcion=motivo,
    )
    return producto_fuente


def reasignar_producto_canonico(producto_fuente, producto_canonico):
    antes = {"producto_canonico_id": producto_fuente.producto_canonico_id}
    producto_fuente.producto_canonico = producto_canonico
    producto_fuente.save(update_fields=["producto_canonico", "fecha_actualizacion"])
    if producto_canonico:
        calcular_comparacion_producto(producto_canonico)
        evaluar_producto_multifuente(producto_canonico)
    OperacionCuraduria.objects.create(
        tipo_operacion=OperacionCuraduria.TIPO_REASIGNAR,
        producto_fuente=producto_fuente,
        producto_canonico=producto_canonico,
        descripcion="ProductoFuente reasignado a ProductoCanonico.",
        datos_antes=json.dumps(antes),
        datos_despues=json.dumps({"producto_canonico_id": producto_canonico.pk if producto_canonico else None}),
    )
    return producto_fuente


@transaction.atomic
def fusionar_producto_fuente(origen_id, destino_id):
    origen = ProductoFuente.objects.select_for_update().get(pk=origen_id)
    destino = ProductoFuente.objects.select_for_update().get(pk=destino_id)
    PrecioFuente.objects.filter(producto_fuente=origen).update(producto_fuente=destino)
    ResultadoExtraccionWeb.objects.filter(producto_fuente=origen).update(producto_fuente=destino)
    origen.requiere_revision = True
    origen.motivo_revision = "Fusionado con otro ProductoFuente. Mantener solo como referencia historica."
    origen.save(update_fields=["requiere_revision", "motivo_revision", "fecha_actualizacion"])
    if destino.producto_canonico:
        calcular_comparacion_producto(destino.producto_canonico)
        evaluar_producto_multifuente(destino.producto_canonico)
    OperacionCuraduria.objects.create(
        tipo_operacion=OperacionCuraduria.TIPO_FUSIONAR,
        producto_fuente=destino,
        producto_canonico=destino.producto_canonico,
        descripcion=f"ProductoFuente #{origen.pk} fusionado en #{destino.pk}.",
    )
    return destino


def marcar_revisado(producto_fuente):
    producto_fuente.revisado = True
    producto_fuente.requiere_revision = False
    producto_fuente.fecha_revision = timezone.now()
    producto_fuente.save(update_fields=["revisado", "requiere_revision", "fecha_revision", "fecha_actualizacion"])
    OperacionCuraduria.objects.create(
        tipo_operacion=OperacionCuraduria.TIPO_REVISAR,
        producto_fuente=producto_fuente,
        producto_canonico=producto_fuente.producto_canonico,
        descripcion="Producto marcado como revisado.",
    )
    return producto_fuente


def crear_producto_canonico_desde_fuente(producto_fuente):
    categoria = producto_fuente.producto_canonico.categoria if producto_fuente.producto_canonico else None
    if not categoria:
        from oportunidades.models import CategoriaInteres

        categoria, _ = CategoriaInteres.objects.get_or_create(
            nombre="Sin clasificar",
            defaults={"palabra_clave": "sin clasificar", "prioridad": 99},
        )
    producto, _ = ProductoCanonico.objects.get_or_create(
        nombre_normalizado=normalizar_titulo_para_dedupe(producto_fuente.titulo_original),
        categoria=categoria,
        marca=producto_fuente.marca_detectada,
    )
    return producto
