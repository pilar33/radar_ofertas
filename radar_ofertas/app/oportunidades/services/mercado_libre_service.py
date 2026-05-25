import json
import os
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import requests
from django.db import transaction
from django.utils import timezone

from oportunidades.models import (
    CategoriaInteres,
    ConsultaMercadoLibre,
    FuenteProducto,
    MercadoLibreToken,
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


def _env(nombre, default=""):
    valor = os.getenv(nombre)
    if valor is None or str(valor).strip() == "":
        return default
    return str(valor).strip()


def get_meli_config():
    return {
        "base_url": _env("MELI_BASE_URL", "https://api.mercadolibre.com").rstrip("/"),
        "auth_base_url": _env("MELI_AUTH_BASE_URL", "https://auth.mercadolibre.com.ar").rstrip("/"),
        "site_id": _env("MELI_SITE_ID", "MLA"),
        "client_id": _env("MELI_CLIENT_ID"),
        "client_secret": _env("MELI_CLIENT_SECRET"),
        "redirect_uri": _env("MELI_REDIRECT_URI", "http://localhost:8000/mercadolibre/oauth/callback/"),
        "access_token": _env("MELI_ACCESS_TOKEN"),
        "refresh_token": _env("MELI_REFRESH_TOKEN"),
        "search_limit_default": _int(os.getenv("MELI_SEARCH_LIMIT_DEFAULT"), 20),
        "timeout": _int(os.getenv("MELI_REQUEST_TIMEOUT"), 15),
        "user_agent": _env("MELI_USER_AGENT", "radar_ofertas/1.0"),
        "affiliate_tag": _env("MELI_AFFILIATE_TAG"),
        "affiliate_base_url": _env("MELI_AFFILIATE_BASE_URL"),
    }


def obtener_token_activo():
    ahora = timezone.now()
    token_db = (
        MercadoLibreToken.objects.filter(activo=True)
        .filter(expires_at__gt=ahora)
        .order_by("-fecha_actualizacion", "-id")
        .first()
    )
    if token_db and token_db.access_token:
        return token_db.access_token

    config = get_meli_config()
    return config["access_token"] or None


def get_headers(use_auth=True):
    config = get_meli_config()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": config["user_agent"],
        "Accept-Language": "es-AR,es;q=0.9",
        "Connection": "keep-alive",
    }

    token = obtener_token_activo() if use_auth else None
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def _limitar_texto(texto, limite=500):
    if texto is None:
        return ""
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8", errors="replace")
    if not isinstance(texto, str):
        texto = "" if texto.__class__.__module__.startswith("unittest.mock") else str(texto)
    return texto[:limite]


def _response_text(response):
    return _limitar_texto(getattr(response, "text", "") or "")


def _resultado_error(status_code=None, error="", requires_token=False, forbidden=False, response_text=""):
    return {
        "ok": False,
        "status_code": status_code,
        "data": None,
        "error": error,
        "error_message": error,
        "response_text": _limitar_texto(response_text),
        "requires_token": requires_token,
        "forbidden": forbidden,
    }


def request_meli(method, endpoint, params=None, data=None, use_auth=True):
    config = get_meli_config()
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{config['base_url']}{endpoint}"

    try:
        response = requests.request(
            method,
            url,
            headers=get_headers(use_auth=use_auth),
            params=params,
            json=data,
            timeout=config["timeout"],
        )
        status_code = response.status_code

        if status_code == 403:
            return _resultado_error(
                status_code=403,
                forbidden=True,
                requires_token=True,
                response_text=_response_text(response),
                error=(
                    "Mercado Libre devolvio 403 Forbidden. Puede requerir token Bearer, "
                    "headers validos o revision de permisos/restricciones del endpoint."
                ),
            )
        if status_code == 401:
            return _resultado_error(
                status_code=401,
                requires_token=True,
                response_text=_response_text(response),
                error="Mercado Libre devolvio 401 Unauthorized. El token puede estar ausente, vencido o no autorizado.",
            )
        if status_code == 429:
            return _resultado_error(
                status_code=429,
                response_text=_response_text(response),
                error="Mercado Libre devolvio 429 Too Many Requests. Se alcanzo un limite de consultas.",
            )

        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError as exc:
            return _resultado_error(
                status_code=status_code,
                response_text=_response_text(response),
                error=f"Respuesta JSON invalida de Mercado Libre: {exc}",
            )

        return {
            "ok": True,
            "status_code": status_code,
            "data": payload,
            "error": None,
            "requires_token": False,
            "forbidden": False,
        }
    except requests.exceptions.Timeout as exc:
        return _resultado_error(error=f"Timeout conectando con Mercado Libre: {exc}")
    except requests.exceptions.ConnectionError as exc:
        return _resultado_error(error=f"Error de conexion con Mercado Libre: {exc}")
    except requests.exceptions.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None) or getattr(response, "status_code", None)
        response_text = _response_text(getattr(exc, "response", None) or locals().get("response"))
        return _resultado_error(status_code=status_code, response_text=response_text, error=f"Error HTTP Mercado Libre: {exc}")
    except requests.exceptions.RequestException as exc:
        return _resultado_error(error=f"Error consultando Mercado Libre: {exc}")


def buscar_productos(query, limit=20, offset=0, site_id=None, usar_token_si_existe=True):
    config = get_meli_config()
    site_id = site_id or config["site_id"]
    limit = _int(limit, config["search_limit_default"])
    offset = _int(offset, 0)
    use_auth = bool(usar_token_si_existe and obtener_token_activo())
    respuesta = request_meli(
        "GET",
        f"/sites/{site_id}/search",
        params={"q": query, "limit": limit, "offset": offset},
        use_auth=use_auth,
    )

    if not respuesta["ok"]:
        error = respuesta["error"]
        if respuesta["forbidden"] and not use_auth:
            error = f"{error} Configura MELI_ACCESS_TOKEN o autoriza la aplicacion via OAuth."
        elif respuesta["forbidden"] and use_auth:
            error = f"{error} Revisa permisos de la app, token, scopes o endpoint."
        return {
            "ok": False,
            "results": [],
            "paging": {},
            "status_code": respuesta["status_code"],
            "error": error,
            "error_message": error,
            "response_text": respuesta.get("response_text", ""),
            "requires_token": respuesta["requires_token"],
            "forbidden": respuesta["forbidden"],
            "site_id": site_id,
            "uso_token": use_auth,
        }

    data = respuesta["data"] or {}
    return {
        "ok": True,
        "results": data.get("results") or [],
        "paging": data.get("paging") or {},
        "status_code": respuesta["status_code"],
        "error": None,
        "requires_token": False,
        "forbidden": False,
        "site_id": site_id,
        "uso_token": use_auth,
    }


def obtener_detalle_producto(item_id, usar_token_si_existe=True):
    if not item_id:
        return {
            "ok": False,
            "status_code": None,
            "data": None,
            "error": "item_id requerido.",
            "error_message": "item_id requerido.",
            "response_text": "",
            "requires_token": False,
            "forbidden": False,
        }

    use_auth = bool(usar_token_si_existe and obtener_token_activo())
    return request_meli("GET", f"/items/{item_id}", use_auth=use_auth)


def _diagnostico_resultado(nombre, usa_token, resultado):
    return {
        "nombre": nombre,
        "usa_token": usa_token,
        "status_code": resultado.get("status_code"),
        "ok": bool(resultado.get("ok")),
        "error": resultado.get("error") or resultado.get("error_message"),
        "response_text": _limitar_texto(resultado.get("response_text")),
        "requires_token": bool(resultado.get("requires_token")),
        "forbidden": bool(resultado.get("forbidden")),
    }


def diagnosticar_endpoints_meli(query="calza mujer", item_id="MLA3092462776", limit=1):
    config = get_meli_config()
    site_id = config["site_id"]
    token_disponible = bool(obtener_token_activo())
    resultados = []

    users_me = request_meli("GET", "/users/me", use_auth=token_disponible)
    resultados.append(_diagnostico_resultado("users/me", token_disponible, users_me))

    categorias = request_meli("GET", f"/sites/{site_id}/categories", use_auth=False)
    resultados.append(_diagnostico_resultado("sites categories", False, categorias))

    search_sin_token = request_meli(
        "GET",
        f"/sites/{site_id}/search",
        params={"q": query, "limit": limit, "offset": 0},
        use_auth=False,
    )
    resultados.append(_diagnostico_resultado("search sin token", False, search_sin_token))

    search_con_token = request_meli(
        "GET",
        f"/sites/{site_id}/search",
        params={"q": query, "limit": limit, "offset": 0},
        use_auth=token_disponible,
    )
    resultados.append(_diagnostico_resultado("search con token", token_disponible, search_con_token))

    detalle = request_meli("GET", f"/items/{item_id}", use_auth=token_disponible)
    resultados.append(_diagnostico_resultado("item detail con token", token_disponible, detalle))

    return {
        "query": query,
        "item_id": item_id,
        "limit": limit,
        "token_disponible": token_disponible,
        "resultados": resultados,
        "interpretacion": interpretar_diagnostico_meli(resultados),
    }


def _por_nombre(resultados, nombre):
    for resultado in resultados:
        if resultado["nombre"] == nombre:
            return resultado
    return {}


def interpretar_diagnostico_meli(resultados):
    users_me = _por_nombre(resultados, "users/me")
    categorias = _por_nombre(resultados, "sites categories")
    search_con_token = _por_nombre(resultados, "search con token")
    search_sin_token = _por_nombre(resultados, "search sin token")
    search = search_con_token or search_sin_token

    if users_me.get("ok") and search.get("status_code") == 403:
        return "OAuth y token funcionan. El problema esta en el endpoint de busqueda general, que Mercado Libre esta restringiendo para esta app/token."
    if users_me.get("status_code") == 401:
        return "El token es invalido o vencido. Reautorizar Mercado Libre."
    if users_me.get("status_code") == 403:
        return "El token existe pero no tiene permisos suficientes o la app no esta habilitada para consultar este recurso."
    if categorias.get("ok") and search.get("status_code") == 403:
        return "La conectividad con Mercado Libre funciona, pero la busqueda de productos esta restringida."
    if not any(resultado.get("ok") for resultado in resultados):
        return "Puede haber bloqueo de red, headers, token invalido o restriccion general."

    return "Diagnostico mixto. Revisar status_code y respuesta de cada endpoint."


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


def sincronizar_busqueda_meli(query, categoria=None, limit=20, offset=0, usar_token_si_existe=True):
    config = get_meli_config()
    limit = _int(limit, config["search_limit_default"])
    offset = _int(offset, 0)
    respuesta = buscar_productos(
        query,
        limit=limit,
        offset=offset,
        site_id=config["site_id"],
        usar_token_si_existe=usar_token_si_existe,
    )
    results = respuesta.get("results") or []

    mensaje_error = respuesta.get("error")
    if mensaje_error and respuesta.get("response_text"):
        mensaje_error = f"{mensaje_error} Respuesta: {respuesta['response_text']}"

    ConsultaMercadoLibre.objects.create(
        categoria=categoria,
        query=query,
        site_id=respuesta.get("site_id") or config["site_id"],
        limit=limit,
        offset=offset,
        cantidad_resultados=len(results),
        exitosa=bool(respuesta.get("ok")),
        status_code=respuesta.get("status_code"),
        requiere_token=bool(respuesta.get("requires_token")),
        forbidden=bool(respuesta.get("forbidden")),
        uso_token=bool(respuesta.get("uso_token")),
        mensaje_error=mensaje_error,
    )

    resumen = {
        "query": query,
        "procesados": 0,
        "creados": 0,
        "actualizados": 0,
        "errores": 0,
        "mensaje": respuesta.get("error"),
        "response_text": respuesta.get("response_text", ""),
        "status_code": respuesta.get("status_code"),
        "requires_token": bool(respuesta.get("requires_token")),
        "forbidden": bool(respuesta.get("forbidden")),
        "uso_token": bool(respuesta.get("uso_token")),
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
        except Exception as exc:
            resumen["errores"] += 1
            resumen["mensaje"] = f"Error procesando item de Mercado Libre: {exc}"

    return resumen


def generar_url_autorizacion():
    config = get_meli_config()
    if not config["client_id"] or not config["redirect_uri"]:
        return {
            "ok": False,
            "url": None,
            "error": "Faltan MELI_CLIENT_ID o MELI_REDIRECT_URI para iniciar OAuth.",
        }

    params = {
        "response_type": "code",
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
    }
    return {
        "ok": True,
        "url": f"{config['auth_base_url']}/authorization?{urlencode(params)}",
        "error": None,
    }


def _guardar_token(data):
    expires_in = _int(data.get("expires_in"), 0)
    expires_at = timezone.now() + timezone.timedelta(seconds=expires_in) if expires_in else None
    user_id = data.get("user_id")

    token, _ = MercadoLibreToken.objects.update_or_create(
        user_id_meli=str(user_id) if user_id else None,
        defaults={
            "access_token": data.get("access_token") or "",
            "refresh_token": data.get("refresh_token"),
            "token_type": data.get("token_type"),
            "scope": data.get("scope"),
            "expires_in": expires_in,
            "expires_at": expires_at,
            "activo": True,
        },
    )
    return token


def _oauth_post(payload):
    config = get_meli_config()
    respuesta = request_meli("POST", "/oauth/token", data=payload, use_auth=False)
    if not respuesta["ok"]:
        return {**respuesta, "token": None}

    token = _guardar_token(respuesta["data"] or {})
    return {**respuesta, "token": token}


def intercambiar_code_por_token(code):
    config = get_meli_config()
    if not code:
        return _resultado_error(error="Codigo OAuth requerido.")
    if not config["client_id"] or not config["client_secret"] or not config["redirect_uri"]:
        return _resultado_error(error="Faltan MELI_CLIENT_ID, MELI_CLIENT_SECRET o MELI_REDIRECT_URI.")

    return _oauth_post(
        {
            "grant_type": "authorization_code",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "redirect_uri": config["redirect_uri"],
        }
    )


def refrescar_token(refresh_token=None):
    config = get_meli_config()
    token_db = MercadoLibreToken.objects.filter(activo=True).order_by("-fecha_actualizacion", "-id").first()
    refresh_token = refresh_token or (token_db.refresh_token if token_db else None) or config["refresh_token"]

    if not refresh_token:
        return _resultado_error(error="No hay refresh_token disponible.")
    if not config["client_id"] or not config["client_secret"]:
        return _resultado_error(error="Faltan MELI_CLIENT_ID o MELI_CLIENT_SECRET.")

    return _oauth_post(
        {
            "grant_type": "refresh_token",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "refresh_token": refresh_token,
        }
    )


def preparar_link_afiliado(producto):
    config = get_meli_config()

    if producto.url_afiliado:
        return {
            "url": producto.url_afiliado,
            "mensaje": "Link afiliado cargado en el producto.",
            "configurado": True,
        }

    if config["affiliate_base_url"] and config["affiliate_tag"]:
        separador = "&" if "?" in producto.url else "?"
        url = f"{producto.url}{separador}{urlencode({'utm_source': config['affiliate_tag']})}"
        return {
            "url": url,
            "mensaje": "Link afiliado preparado con configuracion local. Validar formato antes de usar.",
            "configurado": True,
        }

    return {
        "url": producto.url,
        "mensaje": "Link afiliado no configurado. Cargar manualmente url_afiliado cuando se obtenga desde la central de afiliados.",
        "configurado": False,
    }


def buscar_productos_por_categoria(categoria, limit=20, offset=0):
    return sincronizar_busqueda_meli(categoria.palabra_clave, categoria=categoria, limit=limit, offset=offset)


def obtener_link_afiliado(producto):
    return preparar_link_afiliado(producto)
