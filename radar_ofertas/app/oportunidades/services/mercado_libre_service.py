import json
import os
from decimal import Decimal, InvalidOperation

import requests
from django.db import transaction

from oportunidades.models import (
    CategoriaInteres,
    ConsultaMercadoLibre,
    FuenteProducto,
    Oportunidad,
    PrecioProducto,
    Producto,
)
from oportunidades.services.clasificacion_service import clasificar_oportunidad


def _decimal(valor):
    try:
        return Decimal(str(valor or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _int(valor, default=0):
    try:
        return int(valor or default)
    except (TypeError, ValueError):
        return default


def get_meli_config():
    return {
        "base_url": os.getenv("MELI_BASE_URL", "https://api.mercadolibre.com").rstrip("/"),
        "site_id": os.getenv("MELI_SITE_ID", "MLA"),
        "search_limit_default": _int(os.getenv("MELI_SEARCH_LIMIT_DEFAULT"), 20),
        "request_timeout": _int(os.getenv("MELI_REQUEST_TIMEOUT"), 15),
        "access_token": os.getenv("MELI_ACCESS_TOKEN", "").strip(),
    }


def get_headers():
    config = get_meli_config()
    headers = {
        "Accept": "application/json",
        "User-Agent": "radar_ofertas/1.0",
    }

    if config["access_token"]:
        headers["Authorization"] = f"Bearer {config['access_token']}"

    return headers


def buscar_productos(query, limit=20, offset=0, site_id=None):
    config = get_meli_config()
    site_id = site_id or config["site_id"]
    limit = _int(limit, config["search_limit_default"])
    offset = _int(offset, 0)
    url = f"{config['base_url']}/sites/{site_id}/search"

    try:
        response = requests.get(
            url,
            headers=get_headers(),
            params={"q": query, "limit": limit, "offset": offset},
            timeout=config["request_timeout"],
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or []
        return {
            "ok": True,
            "results": results,
            "paging": data.get("paging") or {},
            "error": None,
            "site_id": site_id,
        }
    except requests.exceptions.HTTPError as exc:
        return {"ok": False, "results": [], "paging": {}, "error": f"Error HTTP Mercado Libre: {exc}", "site_id": site_id}
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "results": [], "paging": {}, "error": f"Error de conexion Mercado Libre: {exc}", "site_id": site_id}
    except ValueError as exc:
        return {"ok": False, "results": [], "paging": {}, "error": f"Respuesta invalida Mercado Libre: {exc}", "site_id": site_id}


def obtener_detalle_producto(item_id):
    if not item_id:
        return None

    config = get_meli_config()
    url = f"{config['base_url']}/items/{item_id}"

    try:
        response = requests.get(url, headers=get_headers(), timeout=config["request_timeout"])
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, ValueError):
        return None


def _traducir_condicion(condicion):
    mapa = {
        "new": Producto.CONDICION_NUEVO,
        "used": Producto.CONDICION_USADO,
        "reconditioned": Producto.CONDICION_REACONDICIONADO,
    }
    return mapa.get(condicion, Producto.CONDICION_DESCONOCIDO)


def _normalizar_vendedor(item):
    seller = item.get("seller") or {}
    if isinstance(seller, dict):
        return str(seller.get("nickname") or seller.get("id") or "") or None
    return str(seller) if seller else None


def normalizar_resultado_meli(item):
    item = item or {}
    available_quantity = _int(item.get("available_quantity"), 0)

    return {
        "codigo_externo": item.get("id"),
        "titulo": item.get("title") or "Producto sin titulo",
        "url": item.get("permalink") or "",
        "precio": _decimal(item.get("price")),
        "moneda": item.get("currency_id") or "ARS",
        "thumbnail_url": item.get("thumbnail"),
        "vendedor": _normalizar_vendedor(item),
        "condicion": _traducir_condicion(item.get("condition")),
        "cantidad_vendida": _int(item.get("sold_quantity"), 0),
        "disponible": available_quantity > 0,
        "raw_data": json.dumps(item, ensure_ascii=False),
    }


def _obtener_fuente_meli():
    fuente, _ = FuenteProducto.objects.get_or_create(
        nombre="Mercado Libre",
        defaults={
            "tipo": FuenteProducto.TIPO_MARKETPLACE,
            "url_base": "https://www.mercadolibre.com.ar",
            "activa": True,
        },
    )
    return fuente


def _categoria_para_producto(categoria, query):
    if categoria:
        return categoria

    categoria_generica, _ = CategoriaInteres.objects.get_or_create(
        nombre="Mercado Libre - Busqueda manual",
        defaults={
            "palabra_clave": query or "mercado libre",
            "activa": True,
            "prioridad": 99,
        },
    )
    return categoria_generica


@transaction.atomic
def guardar_producto_desde_meli(item_normalizado, categoria):
    fuente = _obtener_fuente_meli()
    codigo_externo = item_normalizado.get("codigo_externo")
    precio = _decimal(item_normalizado.get("precio"))

    producto = Producto.objects.filter(fuente=fuente, codigo_externo=codigo_externo).first()
    datos_producto = {
        "titulo": item_normalizado.get("titulo") or "Producto sin titulo",
        "url": item_normalizado.get("url") or "https://www.mercadolibre.com.ar",
        "marca": None,
        "categoria": categoria,
        "vendedor": item_normalizado.get("vendedor"),
        "condicion": item_normalizado.get("condicion") or Producto.CONDICION_DESCONOCIDO,
        "thumbnail_url": item_normalizado.get("thumbnail_url"),
        "cantidad_vendida": _int(item_normalizado.get("cantidad_vendida"), 0),
        "disponible": bool(item_normalizado.get("disponible")),
        "raw_data": item_normalizado.get("raw_data"),
    }

    if producto:
        for campo, valor in datos_producto.items():
            setattr(producto, campo, valor)
        producto.save(update_fields=list(datos_producto.keys()))
    else:
        producto = Producto.objects.create(
            fuente=fuente,
            codigo_externo=codigo_externo,
            es_chico_liviano=True,
            es_fragil=False,
            **datos_producto,
        )

    ultimo_precio = producto.precios.order_by("-fecha_relevamiento", "-id").first()
    if ultimo_precio and ultimo_precio.precio == precio:
        precio_producto = ultimo_precio
    else:
        precio_producto = PrecioProducto.objects.create(
            producto=producto,
            precio=precio,
            costo_envio=Decimal("0.00"),
            moneda=item_normalizado.get("moneda") or "ARS",
        )

    return producto, precio_producto


@transaction.atomic
def crear_o_actualizar_oportunidad(producto, precio_actual):
    evaluacion = clasificar_oportunidad(producto, precio_actual)
    oportunidad = (
        producto.oportunidades.filter(estado__in=[Oportunidad.ESTADO_PENDIENTE, Oportunidad.ESTADO_REVISADO])
        .order_by("-fecha_creacion", "-id")
        .first()
    )

    datos = {
        "precio_referencia": precio_actual,
        "precio_actual": precio_actual,
        "precio_reventa_estimado": evaluacion["precio_reventa_estimado"],
        "margen_estimado": evaluacion["margen_estimado"],
        "porcentaje_margen": evaluacion["porcentaje_margen"],
        "tipo": evaluacion["tipo"],
        "riesgo": evaluacion["riesgo"],
        "puntaje": evaluacion["puntaje"],
        "motivo": evaluacion["motivo"],
    }

    if oportunidad:
        for campo, valor in datos.items():
            setattr(oportunidad, campo, valor)
        oportunidad.save(update_fields=list(datos.keys()))
    else:
        oportunidad = Oportunidad.objects.create(
            producto=producto,
            estado=Oportunidad.ESTADO_PENDIENTE,
            **datos,
        )

    return oportunidad


def sincronizar_busqueda_meli(query, categoria=None, limit=20, offset=0):
    config = get_meli_config()
    limit = _int(limit, config["search_limit_default"])
    offset = _int(offset, 0)
    respuesta = buscar_productos(query, limit=limit, offset=offset, site_id=config["site_id"])
    results = respuesta.get("results") or []

    ConsultaMercadoLibre.objects.create(
        categoria=categoria,
        query=query,
        site_id=respuesta.get("site_id") or config["site_id"],
        limit=limit,
        offset=offset,
        cantidad_resultados=len(results),
        exitosa=bool(respuesta.get("ok")),
        mensaje_error=respuesta.get("error"),
    )

    resumen = {
        "query": query,
        "procesados": 0,
        "creados": 0,
        "actualizados": 0,
        "errores": 0,
    }

    if not respuesta.get("ok"):
        resumen["errores"] = 1
        return resumen

    for item in results:
        try:
            normalizado = normalizar_resultado_meli(item)
            if not normalizado["codigo_externo"]:
                resumen["errores"] += 1
                continue

            fuente = _obtener_fuente_meli()
            existe = Producto.objects.filter(fuente=fuente, codigo_externo=normalizado["codigo_externo"]).exists()
            categoria_producto = _categoria_para_producto(categoria, query)
            producto, precio_producto = guardar_producto_desde_meli(normalizado, categoria_producto)
            crear_o_actualizar_oportunidad(producto, precio_producto.precio)

            resumen["procesados"] += 1
            if existe:
                resumen["actualizados"] += 1
            else:
                resumen["creados"] += 1
        except Exception:
            resumen["errores"] += 1

    return resumen


def buscar_productos_por_categoria(categoria, limit=20, offset=0):
    return sincronizar_busqueda_meli(categoria.palabra_clave, categoria=categoria, limit=limit, offset=offset)


def obtener_link_afiliado(*args, **kwargs):
    raise NotImplementedError("Integracion de afiliados pendiente para una etapa posterior.")
