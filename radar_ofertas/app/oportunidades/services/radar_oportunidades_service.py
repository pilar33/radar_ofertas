import json
from decimal import Decimal
from difflib import SequenceMatcher

from django.utils import timezone

from oportunidades.models import CandidatoCompra, FuenteWeb, ImportacionRadarTexto, OportunidadRadar, ProductoCanonico, ProductoFuente
from oportunidades.services.normalizacion_service import normalizar_texto_producto
from oportunidades.services.radar_texto_parser_service import calcular_score_radar, parsear_texto_radar


def _similar(a, b):
    return SequenceMatcher(None, normalizar_texto_producto(a or ""), normalizar_texto_producto(b or "")).ratio()


def _vincular_fuente(tienda):
    if not tienda:
        return None
    normalizada = normalizar_texto_producto(tienda)
    for fuente in FuenteWeb.objects.all():
        if normalizar_texto_producto(fuente.nombre) == normalizada or normalizada in normalizar_texto_producto(fuente.nombre):
            return fuente
    return None


def _vincular_producto_fuente(nombre, fuente=None):
    qs = ProductoFuente.objects.select_related("producto_canonico", "fuente_web")
    if fuente:
        qs = qs.filter(fuente_web=fuente)
    mejor = None
    mejor_score = 0
    for producto in qs.order_by("-fecha_actualizacion")[:500]:
        score = _similar(nombre, producto.titulo_original)
        if score > mejor_score:
            mejor = producto
            mejor_score = score
    return mejor if mejor_score >= 0.72 else None


def _vincular_producto_canonico(nombre):
    mejor = None
    mejor_score = 0
    for producto in ProductoCanonico.objects.all()[:500]:
        score = _similar(nombre, producto.nombre_normalizado)
        if score > mejor_score:
            mejor = producto
            mejor_score = score
    return mejor if mejor_score >= 0.72 else None


def _duplicado_reciente(datos):
    desde = timezone.now() - timezone.timedelta(days=7)
    tienda = datos.get("tienda") or ""
    nombre = datos.get("producto_nombre") or ""
    precio = datos.get("precio_actual")
    candidatos = OportunidadRadar.objects.filter(fecha_detectada__gte=desde, tienda__iexact=tienda)
    for oportunidad in candidatos:
        if _similar(nombre, oportunidad.producto_nombre) < 0.86:
            continue
        precio_ok = True
        if precio and oportunidad.precio_actual:
            precio_ok = abs(precio - oportunidad.precio_actual) <= max(Decimal("1.00"), precio * Decimal("0.03"))
        descuento_ok = True
        descuento = datos.get("descuento_real_pct_estimado")
        if descuento and oportunidad.descuento_real_pct_estimado:
            descuento_ok = abs(descuento - oportunidad.descuento_real_pct_estimado) <= Decimal("5.00")
        if precio_ok and descuento_ok:
            return oportunidad
    return None


def _preparar_datos_modelo(datos, importacion=None, origen=OportunidadRadar.ORIGEN_CHATGPT_RADAR):
    fuente = _vincular_fuente(datos.get("tienda"))
    producto_fuente = _vincular_producto_fuente(datos.get("producto_nombre"), fuente)
    producto_canonico = producto_fuente.producto_canonico if producto_fuente else _vincular_producto_canonico(datos.get("producto_nombre"))
    requiere_revision = bool(datos.get("advertencias")) or not datos.get("precio_actual") or not datos.get("precio_comparable_minimo") or not datos.get("url_oferta")
    return {
        "importacion": importacion,
        "titulo": datos.get("titulo") or datos.get("producto_nombre") or "Oportunidad radar",
        "tienda": datos.get("tienda"),
        "producto_nombre": datos.get("producto_nombre") or "Oportunidad detectada",
        "producto_fuente": producto_fuente,
        "producto_canonico": producto_canonico,
        "fuente_web": fuente,
        "precio_actual": datos.get("precio_actual"),
        "precio_comparable_minimo": datos.get("precio_comparable_minimo"),
        "precio_comparable_maximo": datos.get("precio_comparable_maximo"),
        "descuento_real_pct_estimado": datos.get("descuento_real_pct_estimado"),
        "descuento_texto": datos.get("descuento_texto"),
        "comparable_principal_tienda": datos.get("comparable_principal_tienda"),
        "comparable_principal_precio": datos.get("comparable_principal_precio"),
        "comparables_texto": datos.get("comparables_texto"),
        "envio_texto": datos.get("envio_texto"),
        "stock_texto": datos.get("stock_texto"),
        "vendedor_texto": datos.get("vendedor_texto"),
        "motivo_conveniencia": datos.get("motivo_conveniencia"),
        "chequeo_antimarketing": datos.get("chequeo_antimarketing"),
        "riesgo_texto": datos.get("riesgo_texto"),
        "decision_sugerida": datos.get("decision_sugerida") or OportunidadRadar.DECISION_ANALIZAR,
        "score_radar": datos.get("score_radar") or 0,
        "nivel_oportunidad": datos.get("nivel_oportunidad") or OportunidadRadar.NIVEL_DUDOSA,
        "requiere_revision": requiere_revision,
        "origen": origen,
        "texto_original": datos.get("texto_original") or "",
        "texto_parseado": json.dumps(datos, ensure_ascii=False, default=str),
        "url_oferta": datos.get("url_oferta"),
        "url_comparable": datos.get("url_comparable"),
        "estado": OportunidadRadar.ESTADO_IMPORTADA,
    }


def analizar_importacion_radar(texto, origen=ImportacionRadarTexto.ORIGEN_CHATGPT_RADAR):
    oportunidades = parsear_texto_radar(texto)
    importacion = ImportacionRadarTexto.objects.create(
        titulo=f"Importacion Radar {timezone.localtime():%Y-%m-%d %H:%M}",
        texto_original=texto,
        origen=origen,
        estado=ImportacionRadarTexto.ESTADO_ANALIZADA,
        oportunidades_detectadas=len(oportunidades),
        resumen=json.dumps(oportunidades, ensure_ascii=False, default=str),
    )
    return importacion, oportunidades


def importar_oportunidades_desde_texto(texto, origen=OportunidadRadar.ORIGEN_CHATGPT_RADAR, confirmar=True, indices=None, min_score=None):
    oportunidades = parsear_texto_radar(texto)
    importacion = ImportacionRadarTexto.objects.create(
        titulo=f"Importacion Radar {timezone.localtime():%Y-%m-%d %H:%M}",
        texto_original=texto,
        origen=origen if origen in dict(ImportacionRadarTexto.ORIGEN_CHOICES) else ImportacionRadarTexto.ORIGEN_TEXTO_EXTERNO,
        estado=ImportacionRadarTexto.ESTADO_PENDIENTE,
        oportunidades_detectadas=len(oportunidades),
        resumen=json.dumps(oportunidades, ensure_ascii=False, default=str),
    )
    creadas = []
    errores = 0
    seleccion = set(int(i) for i in indices) if indices is not None else None
    for idx, datos in enumerate(oportunidades):
        if seleccion is not None and idx not in seleccion:
            continue
        if min_score is not None and (datos.get("score_radar") or 0) < min_score:
            continue
        if _duplicado_reciente(datos):
            continue
        if not confirmar:
            continue
        try:
            oportunidad = OportunidadRadar.objects.create(**_preparar_datos_modelo(datos, importacion=importacion, origen=origen))
            creadas.append(oportunidad)
        except Exception:
            errores += 1
    importacion.oportunidades_importadas = len(creadas)
    importacion.errores = errores
    if errores:
        importacion.estado = ImportacionRadarTexto.ESTADO_IMPORTADA_CON_ADVERTENCIAS
    else:
        importacion.estado = ImportacionRadarTexto.ESTADO_IMPORTADA if creadas else ImportacionRadarTexto.ESTADO_ANALIZADA
    importacion.save(update_fields=["oportunidades_importadas", "errores", "estado", "fecha_actualizacion"])
    return importacion, creadas, oportunidades


def recalcular_oportunidad_radar(oportunidad):
    datos = json.loads(oportunidad.texto_parseado or "{}") if oportunidad.texto_parseado else {}
    datos.update(
        {
            "precio_actual": oportunidad.precio_actual,
            "precio_comparable_minimo": oportunidad.precio_comparable_minimo,
            "descuento_real_pct_estimado": oportunidad.descuento_real_pct_estimado,
            "motivo_conveniencia": oportunidad.motivo_conveniencia,
            "chequeo_antimarketing": oportunidad.chequeo_antimarketing,
            "stock_texto": oportunidad.stock_texto,
            "envio_texto": oportunidad.envio_texto,
            "vendedor_texto": oportunidad.vendedor_texto,
            "url_oferta": oportunidad.url_oferta,
            "requiere_revision": oportunidad.requiere_revision,
        }
    )
    oportunidad.score_radar = calcular_score_radar(datos)
    if oportunidad.score_radar >= 80:
        oportunidad.nivel_oportunidad = OportunidadRadar.NIVEL_ALTA
    elif oportunidad.score_radar >= 60:
        oportunidad.nivel_oportunidad = OportunidadRadar.NIVEL_MEDIA
    elif oportunidad.score_radar >= 40:
        oportunidad.nivel_oportunidad = OportunidadRadar.NIVEL_BAJA
    else:
        oportunidad.nivel_oportunidad = OportunidadRadar.NIVEL_DUDOSA
    oportunidad.save(update_fields=["score_radar", "nivel_oportunidad"])
    return oportunidad


def marcar_oportunidad_radar_como_candidato(oportunidad):
    if oportunidad.candidato_compra_id:
        return oportunidad.candidato_compra, False
    motivo = "\n".join(
        parte for parte in [oportunidad.motivo_conveniencia, oportunidad.chequeo_antimarketing] if parte
    )
    candidato = CandidatoCompra.objects.create(
        producto_fuente=oportunidad.producto_fuente,
        producto_canonico=oportunidad.producto_canonico,
        producto_texto=oportunidad.producto_nombre,
        tienda_texto=oportunidad.tienda,
        origen_candidato=CandidatoCompra.ORIGEN_RADAR_TEXTO,
        precio_oportunidad_detectado=oportunidad.precio_actual,
        fuente_precio=oportunidad.tienda,
        score_comercial_detectado=oportunidad.score_radar,
        motivo_candidato=motivo,
        motivo=motivo,
        prioridad=CandidatoCompra.PRIORIDAD_ALTA if oportunidad.score_radar >= 80 else CandidatoCompra.PRIORIDAD_MEDIA,
        estado=CandidatoCompra.ESTADO_CANDIDATO,
    )
    oportunidad.candidato_compra = candidato
    oportunidad.estado = OportunidadRadar.ESTADO_CANDIDATA
    oportunidad.save(update_fields=["candidato_compra", "estado"])
    return candidato, True
