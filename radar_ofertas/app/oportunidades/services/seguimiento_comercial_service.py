from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from oportunidades.models import (
    CandidatoCompra, CompraProducto, PublicacionReventa, ResultadoComercialProducto, VentaProducto,
)


ESTADOS_CANDIDATO_ACTIVO = [
    CandidatoCompra.ESTADO_OBSERVADO, CandidatoCompra.ESTADO_CANDIDATO,
    CandidatoCompra.ESTADO_APROBADO_COMPRA, CandidatoCompra.ESTADO_COMPRADO,
    CandidatoCompra.ESTADO_PUBLICADO, CandidatoCompra.ESTADO_VENDIDO_PARCIAL,
]


def _prioridad(score):
    if score >= 75:
        return CandidatoCompra.PRIORIDAD_ALTA
    if score >= 50:
        return CandidatoCompra.PRIORIDAD_MEDIA
    return CandidatoCompra.PRIORIDAD_BAJA


@transaction.atomic
def crear_candidato_desde_producto(producto_fuente, motivo=None):
    existente = producto_fuente.candidaturas_compra.filter(estado__in=ESTADOS_CANDIDATO_ACTIVO).first()
    if existente:
        return existente, False
    precio = producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()
    valor = precio.precio_oportunidad if precio else Decimal("0")
    candidato = CandidatoCompra.objects.create(
        producto_fuente=producto_fuente,
        producto_canonico=producto_fuente.producto_canonico,
        lote_captura=precio.lote_captura if precio and precio.lote_captura_id else producto_fuente.lote_origen,
        precio_oportunidad_detectado=valor,
        fuente_precio=producto_fuente.fuente_web.nombre,
        score_comercial_detectado=producto_fuente.score_comercial,
        score_demanda_detectado=producto_fuente.score_demanda_actual,
        motivo_candidato=motivo or "Marcado manualmente desde ranking comercial.",
        motivo=motivo or "Marcado manualmente desde ranking comercial.",
        precio_compra_estimado=valor,
        prioridad=_prioridad(producto_fuente.score_comercial),
        estado=CandidatoCompra.ESTADO_CANDIDATO,
    )
    recalcular_resultado_comercial(candidato)
    return candidato, True


def aprobar_candidato_compra(candidato):
    candidato.estado = CandidatoCompra.ESTADO_APROBADO_COMPRA
    candidato.fecha_decision = timezone.now()
    candidato.save(update_fields=["estado", "fecha_decision", "fecha_actualizacion"])
    return candidato


def descartar_candidato(candidato, motivo):
    candidato.estado = CandidatoCompra.ESTADO_DESCARTADO
    candidato.motivo_descarte = motivo
    candidato.fecha_decision = timezone.now()
    candidato.save(update_fields=["estado", "motivo_descarte", "fecha_decision", "fecha_actualizacion"])
    recalcular_resultado_comercial(candidato)
    return candidato


def calcular_unidades_disponibles(compra):
    vendidas = compra.ventas.filter(estado=VentaProducto.ESTADO_CONFIRMADA).aggregate(total=Sum("cantidad_vendida"))["total"] or 0
    if compra.estado in {CompraProducto.ESTADO_CANCELADA, CompraProducto.ESTADO_DEVUELTA}:
        return 0
    return compra.cantidad_comprada - vendidas


@transaction.atomic
def registrar_compra(candidato, datos_compra):
    compra = CompraProducto(
        candidato=candidato,
        producto_fuente=candidato.producto_fuente,
        producto_canonico=candidato.producto_canonico,
        lote_captura=candidato.lote_captura,
        fuente_web=candidato.producto_fuente.fuente_web if candidato.producto_fuente_id else None,
        **datos_compra,
    )
    compra.save()
    candidato.estado = CandidatoCompra.ESTADO_COMPRADO
    candidato.fecha_decision = candidato.fecha_decision or timezone.now()
    candidato.save(update_fields=["estado", "fecha_decision", "fecha_actualizacion"])
    recalcular_resultado_comercial(candidato)
    return compra


@transaction.atomic
def registrar_publicacion(compra, datos_publicacion):
    cantidad = int(datos_publicacion.get("cantidad_publicada") or 0)
    disponibles = calcular_unidades_disponibles(compra)
    if cantidad > disponibles:
        raise ValidationError(f"La cantidad publicada supera las {disponibles} unidades disponibles.")
    publicacion = PublicacionReventa.objects.create(
        compra=compra,
        candidato=compra.candidato,
        producto_fuente=compra.producto_fuente,
        producto_canonico=compra.producto_canonico,
        **datos_publicacion,
    )
    compra.candidato.estado = CandidatoCompra.ESTADO_PUBLICADO
    compra.candidato.save(update_fields=["estado", "fecha_actualizacion"])
    recalcular_resultado_comercial(compra.candidato)
    return publicacion


@transaction.atomic
def registrar_venta(compra, datos_venta, publicacion=None):
    cantidad = int(datos_venta.get("cantidad_vendida") or 0)
    disponibles = calcular_unidades_disponibles(compra)
    if cantidad > disponibles:
        raise ValidationError(f"No se pueden confirmar {cantidad} unidades; quedan {disponibles} disponibles.")
    venta = VentaProducto(
        compra=compra,
        publicacion=publicacion,
        candidato=compra.candidato,
        producto_fuente=compra.producto_fuente,
        producto_canonico=compra.producto_canonico,
        **datos_venta,
    )
    venta.save()
    restantes = calcular_unidades_disponibles(compra)
    estado_candidato = CandidatoCompra.ESTADO_VENDIDO_TOTAL if restantes <= 0 else CandidatoCompra.ESTADO_VENDIDO_PARCIAL
    compra.candidato.estado = estado_candidato
    compra.candidato.save(update_fields=["estado", "fecha_actualizacion"])
    if publicacion:
        publicacion.estado = PublicacionReventa.ESTADO_VENDIDA_TOTAL if restantes <= 0 else PublicacionReventa.ESTADO_VENDIDA_PARCIAL
        publicacion.save(update_fields=["estado", "fecha_actualizacion"])
    recalcular_resultado_comercial(compra.candidato)
    return venta


def _aprendizaje(estado, margen, dias_primera):
    if estado == ResultadoComercialProducto.ESTADO_COMPRADO_SIN_VENDER:
        return "No registra ventas."
    if estado == ResultadoComercialProducto.ESTADO_VENTA_PARCIAL:
        return "Venta parcial."
    if estado == ResultadoComercialProducto.ESTADO_VENDIDO_CON_PERDIDA:
        return "Perdida."
    if estado == ResultadoComercialProducto.ESTADO_VENDIDO_SIN_GANANCIA or margen < 10:
        return "Margen bajo."
    if estado == ResultadoComercialProducto.ESTADO_VENDIDO_CON_GANANCIA and dias_primera is not None and dias_primera <= 7 and margen >= 25:
        return "Vendio rapido con margen alto. Buen candidato para repetir."
    if estado == ResultadoComercialProducto.ESTADO_VENDIDO_CON_GANANCIA:
        return "Buen candidato para repetir."
    return "Sin resultado comercial suficiente."


@transaction.atomic
def recalcular_resultado_comercial(candidato):
    compras = candidato.compras.exclude(estado__in=[CompraProducto.ESTADO_CANCELADA, CompraProducto.ESTADO_DEVUELTA])
    ventas = VentaProducto.objects.filter(compra__candidato=candidato, estado=VentaProducto.ESTADO_CONFIRMADA)
    cantidad_comprada = compras.aggregate(total=Sum("cantidad_comprada"))["total"] or 0
    cantidad_vendida = ventas.aggregate(total=Sum("cantidad_vendida"))["total"] or 0
    inversion = compras.aggregate(total=Sum("costo_total"))["total"] or Decimal("0")
    ingreso = ventas.aggregate(total=Sum("ingreso_bruto"))["total"] or Decimal("0")
    ganancia = ventas.aggregate(total=Sum("ganancia_neta"))["total"] or Decimal("0")
    margen = ganancia / inversion * 100 if inversion > 0 else Decimal("0")
    promedio_compra = inversion / cantidad_comprada if cantidad_comprada else Decimal("0")
    promedio_venta = ingreso / cantidad_vendida if cantidad_vendida else Decimal("0")
    primera_compra = compras.order_by("fecha_compra", "id").first()
    primera_venta = ventas.order_by("fecha_venta", "id").first()
    ultima_venta = ventas.order_by("-fecha_venta", "-id").first()
    dias_primera = (primera_venta.fecha_venta - primera_compra.fecha_compra).days if primera_compra and primera_venta else None
    disponible = cantidad_comprada - cantidad_vendida
    dias_total = (ultima_venta.fecha_venta - primera_compra.fecha_compra).days if primera_compra and ultima_venta and disponible <= 0 else None
    if candidato.estado == CandidatoCompra.ESTADO_DESCARTADO and not cantidad_comprada:
        estado = ResultadoComercialProducto.ESTADO_DESCARTADO
    elif not cantidad_comprada:
        estado = ResultadoComercialProducto.ESTADO_SIN_COMPRA
    elif not cantidad_vendida:
        estado = ResultadoComercialProducto.ESTADO_COMPRADO_SIN_VENDER
    elif disponible > 0:
        estado = ResultadoComercialProducto.ESTADO_VENTA_PARCIAL
    elif ganancia > 0:
        estado = ResultadoComercialProducto.ESTADO_VENDIDO_CON_GANANCIA
    elif ganancia < 0:
        estado = ResultadoComercialProducto.ESTADO_VENDIDO_CON_PERDIDA
    else:
        estado = ResultadoComercialProducto.ESTADO_VENDIDO_SIN_GANANCIA
    resultado, _ = ResultadoComercialProducto.objects.update_or_create(
        candidato=candidato,
        defaults={
            "producto_fuente": candidato.producto_fuente, "producto_canonico": candidato.producto_canonico,
            "cantidad_comprada_total": cantidad_comprada, "cantidad_vendida_total": cantidad_vendida,
            "cantidad_disponible": disponible, "inversion_total": inversion, "ingreso_total": ingreso,
            "ganancia_neta_total": ganancia, "margen_real_pct": margen,
            "precio_promedio_compra": promedio_compra, "precio_promedio_venta": promedio_venta,
            "dias_hasta_primera_venta": max(0, dias_primera) if dias_primera is not None else None,
            "dias_hasta_venta_total": max(0, dias_total) if dias_total is not None else None,
            "estado_resultado": estado, "aprendizaje": _aprendizaje(estado, margen, dias_primera),
        },
    )
    return resultado
