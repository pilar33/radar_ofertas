import json
import re
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.db import transaction
from django.utils import timezone

from oportunidades.models import (
    CategoriaInteres,
    DetalleImportacionProducto,
    ImportacionProductos,
    PrecioFuente,
    Producto,
    ProductoCanonico,
    ProductoFuente,
)
from oportunidades.services.comparacion_service import calcular_comparacion_producto
from oportunidades.services.evaluacion_multifuente_service import evaluar_producto_multifuente
from oportunidades.services.normalizacion_service import normalizar_texto_producto


COLUMNAS_ALIASES = {
    "titulo": ["titulo", "title", "producto", "nombre", "nombre_producto"],
    "precio": ["precio", "price", "precio_actual", "importe"],
    "codigo_externo": ["codigo", "sku", "id", "codigo_externo"],
    "url_producto": ["url", "link", "enlace", "url_producto"],
    "categoria": ["categoria", "category", "rubro"],
    "marca": ["marca", "brand"],
    "descripcion": ["descripcion", "description", "detalle"],
    "imagen_url": ["imagen", "image", "thumbnail", "foto", "imagen_url"],
    "vendedor": ["vendedor", "seller", "proveedor"],
    "condicion": ["condicion", "condition", "estado_producto"],
    "disponible": ["disponible", "available", "activo"],
    "stock": ["stock", "stock_texto"],
    "precio_lista": ["precio_lista", "list_price", "precio_original"],
    "descuento_porcentaje": ["descuento", "descuento_porcentaje", "discount"],
    "costo_envio": ["envio", "costo_envio", "shipping_cost"],
    "moneda": ["moneda", "currency", "currency_id"],
}


def _es_vacio(valor):
    return valor is None or (isinstance(valor, float) and pd.isna(valor)) or str(valor).strip() == ""


def _valor_texto(valor, default=""):
    if _es_vacio(valor):
        return default
    return str(valor).strip()


def detectar_tipo_archivo(archivo):
    nombre = getattr(archivo, "name", str(archivo)).lower()
    if nombre.endswith(".csv"):
        return ImportacionProductos.TIPO_CSV
    if nombre.endswith(".xlsx"):
        return ImportacionProductos.TIPO_XLSX
    if nombre.endswith(".xls"):
        return ImportacionProductos.TIPO_XLS
    return ImportacionProductos.TIPO_DESCONOCIDO


def leer_archivo_productos(importacion):
    tipo = importacion.tipo_archivo or detectar_tipo_archivo(importacion.archivo)
    try:
        if tipo == ImportacionProductos.TIPO_CSV:
            try:
                df = pd.read_csv(importacion.archivo.path, dtype=str, keep_default_na=False)
            except UnicodeDecodeError:
                df = pd.read_csv(importacion.archivo.path, dtype=str, keep_default_na=False, encoding="latin1")
        elif tipo in {ImportacionProductos.TIPO_XLSX, ImportacionProductos.TIPO_XLS}:
            df = pd.read_excel(importacion.archivo.path, dtype=str, keep_default_na=False)
        else:
            return {"ok": False, "df": None, "error": "Tipo de archivo no soportado."}
    except Exception as exc:
        return {"ok": False, "df": None, "error": f"No se pudo leer el archivo: {exc}"}

    return {"ok": True, "df": df, "error": None}


def _normalizar_nombre_columna(nombre):
    texto = normalizar_texto_producto(str(nombre or ""))
    texto = texto.replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", texto)


def normalizar_columnas_importacion(df):
    columnas_originales = {columna: _normalizar_nombre_columna(columna) for columna in df.columns}
    mapa_inverso = {}
    for campo, aliases in COLUMNAS_ALIASES.items():
        for alias in aliases:
            mapa_inverso[_normalizar_nombre_columna(alias)] = campo

    renombres = {}
    for original, normalizada in columnas_originales.items():
        renombres[original] = mapa_inverso.get(normalizada, normalizada)

    return df.rename(columns=renombres)


def parsear_decimal(valor):
    if _es_vacio(valor):
        return None

    texto = str(valor).strip()
    texto = texto.replace("$", "").replace("ARS", "").replace(" ", "")
    texto = re.sub(r"[^0-9,.\-]", "", texto)
    if not texto or texto in {"-", ",", "."}:
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
        if len(partes) > 2 or (len(partes[-1]) == 3 and all(len(parte) <= 3 for parte in partes[1:])):
            texto = texto.replace(".", "")

    try:
        return Decimal(texto).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def validar_fila_producto(row):
    errores = []
    if _es_vacio(row.get("titulo")):
        errores.append("Falta titulo.")
    if parsear_decimal(row.get("precio")) is None:
        errores.append("Falta precio valido.")
    return errores


def obtener_o_crear_categoria_desde_texto(texto_categoria, categoria_default=None):
    texto = _valor_texto(texto_categoria)
    if texto:
        categoria = CategoriaInteres.objects.filter(nombre__iexact=texto).first()
        if categoria:
            return categoria
    if categoria_default:
        return categoria_default
    categoria, _ = CategoriaInteres.objects.get_or_create(
        nombre="Sin clasificar",
        defaults={"palabra_clave": "sin clasificar", "activa": True, "prioridad": 99},
    )
    return categoria


def obtener_o_crear_producto_canonico(row, categoria):
    titulo = _valor_texto(row.get("titulo"))
    nombre_normalizado = normalizar_texto_producto(titulo)
    marca = _valor_texto(row.get("marca")) or None
    producto = ProductoCanonico.objects.filter(
        nombre_normalizado=nombre_normalizado,
        categoria=categoria,
        marca=marca,
    ).first()
    if producto:
        return producto, False
    return (
        ProductoCanonico.objects.create(
            nombre_normalizado=nombre_normalizado,
            categoria=categoria,
            marca=marca,
            descripcion_normalizada=_valor_texto(row.get("descripcion")) or None,
            es_chico_liviano=bool(row.get("es_chico_liviano", False)),
            es_fragil=bool(row.get("es_fragil", False)),
        ),
        True,
    )


def _buscar_producto_fuente(row, fuente_web):
    codigo = _valor_texto(row.get("codigo_externo")) or None
    url = _valor_texto(row.get("url_producto")) or None
    if codigo:
        producto = ProductoFuente.objects.filter(fuente_web=fuente_web, codigo_externo=codigo).first()
        if producto:
            return producto
    if url:
        producto = ProductoFuente.objects.filter(fuente_web=fuente_web, url_producto=url).first()
        if producto:
            return producto

    titulo_normalizado = normalizar_texto_producto(_valor_texto(row.get("titulo")))
    for producto in ProductoFuente.objects.filter(fuente_web=fuente_web, codigo_externo__isnull=True):
        if normalizar_texto_producto(producto.titulo_original) == titulo_normalizado:
            return producto
    return None


def _normalizar_condicion(valor):
    condicion = normalizar_texto_producto(_valor_texto(valor))
    if condicion in {Producto.CONDICION_NUEVO, Producto.CONDICION_USADO, Producto.CONDICION_REACONDICIONADO}:
        return condicion
    return Producto.CONDICION_DESCONOCIDO


def _parsear_bool(valor, default=True):
    if _es_vacio(valor):
        return default
    texto = normalizar_texto_producto(str(valor))
    if texto in {"1", "si", "sí", "true", "activo", "disponible", "yes"}:
        return True
    if texto in {"0", "no", "false", "inactivo", "agotado"}:
        return False
    return default


def crear_o_actualizar_producto_fuente(row, fuente_web, categoria, producto_canonico, actualizar=True):
    producto = _buscar_producto_fuente(row, fuente_web)
    creado = producto is None
    datos = {
        "producto_canonico": producto_canonico,
        "fuente_web": fuente_web,
        "codigo_externo": _valor_texto(row.get("codigo_externo")) or None,
        "titulo_original": _valor_texto(row.get("titulo")),
        "url_producto": _valor_texto(row.get("url_producto")) or fuente_web.url_base,
        "imagen_url": _valor_texto(row.get("imagen_url")) or None,
        "marca_detectada": _valor_texto(row.get("marca")) or None,
        "descripcion_original": _valor_texto(row.get("descripcion")) or None,
        "vendedor": _valor_texto(row.get("vendedor")) or None,
        "condicion": _normalizar_condicion(row.get("condicion")),
        "disponible": _parsear_bool(row.get("disponible"), default=True),
        "stock_texto": _valor_texto(row.get("stock")) or None,
        "raw_data": json.dumps({k: _valor_texto(v) for k, v in dict(row).items()}, ensure_ascii=True),
    }
    if creado:
        producto = ProductoFuente.objects.create(**datos)
        return producto, True, False
    if actualizar:
        for campo, valor in datos.items():
            setattr(producto, campo, valor)
        producto.save()
        return producto, False, True
    return producto, False, False


def crear_precio_fuente(producto_fuente, row, crear_si_no_cambio=False):
    precio = parsear_decimal(row.get("precio"))
    if precio is None:
        return None, False

    ultimo_precio = producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()
    if ultimo_precio and ultimo_precio.precio == precio and not crear_si_no_cambio:
        return ultimo_precio, False

    precio_fuente = PrecioFuente.objects.create(
        producto_fuente=producto_fuente,
        precio=precio,
        precio_lista=parsear_decimal(row.get("precio_lista")) or Decimal("0.00"),
        descuento_porcentaje=parsear_decimal(row.get("descuento_porcentaje")) or Decimal("0.00"),
        costo_envio=parsear_decimal(row.get("costo_envio")) or Decimal("0.00"),
        moneda=_valor_texto(row.get("moneda"), "ARS") or "ARS",
        origen_dato=row.get("origen_dato") or PrecioFuente.ORIGEN_CSV_EXCEL,
        observaciones=_valor_texto(row.get("observaciones")) or None,
    )
    return precio_fuente, True


def _recalcular_multifuente(productos_canonicos):
    for producto_canonico in productos_canonicos:
        calcular_comparacion_producto(producto_canonico)
        evaluar_producto_multifuente(producto_canonico)


@transaction.atomic
def procesar_importacion(importacion, opciones=None):
    opciones = opciones or {}
    importacion.estado = ImportacionProductos.ESTADO_PROCESANDO
    importacion.tipo_archivo = importacion.tipo_archivo or detectar_tipo_archivo(importacion.archivo)
    importacion.save(update_fields=["estado", "tipo_archivo"])

    lectura = leer_archivo_productos(importacion)
    if not lectura["ok"]:
        importacion.estado = ImportacionProductos.ESTADO_ERROR
        importacion.mensaje_error = lectura["error"]
        importacion.fecha_procesamiento = timezone.now()
        importacion.save(update_fields=["estado", "mensaje_error", "fecha_procesamiento"])
        return importacion

    df = normalizar_columnas_importacion(lectura["df"])
    importacion.total_filas = len(df.index)
    afectados = set()

    for numero_fila, (_, row) in enumerate(df.iterrows(), start=2):
        datos = row.to_dict()
        errores = validar_fila_producto(datos)
        if errores:
            importacion.errores += 1
            DetalleImportacionProducto.objects.create(
                importacion=importacion,
                numero_fila=numero_fila,
                estado=DetalleImportacionProducto.ESTADO_ERROR,
                mensaje=" ".join(errores),
                datos_originales=json.dumps({k: _valor_texto(v) for k, v in datos.items()}, ensure_ascii=True),
            )
            continue

        try:
            datos["origen_dato"] = opciones.get("origen_dato", PrecioFuente.ORIGEN_CSV_EXCEL)
            categoria = obtener_o_crear_categoria_desde_texto(datos.get("categoria"), opciones.get("categoria_default"))
            producto_canonico = None
            if opciones.get("crear_producto_canonico", True):
                producto_canonico, _ = obtener_o_crear_producto_canonico(datos, categoria)
            producto_fuente, creado, actualizado = crear_o_actualizar_producto_fuente(
                datos,
                importacion.fuente_web,
                categoria,
                producto_canonico,
                actualizar=opciones.get("actualizar_productos_existentes", True),
            )
            precio_fuente, precio_creado = crear_precio_fuente(
                producto_fuente,
                datos,
                crear_si_no_cambio=opciones.get("crear_precio_si_no_cambio", False),
            )
            importacion.filas_procesadas += 1
            importacion.productos_creados += int(creado)
            importacion.productos_actualizados += int(actualizado)
            importacion.precios_creados += int(precio_creado)
            if producto_canonico:
                afectados.add(producto_canonico.pk)
            DetalleImportacionProducto.objects.create(
                importacion=importacion,
                numero_fila=numero_fila,
                estado=DetalleImportacionProducto.ESTADO_PROCESADA,
                mensaje="Producto procesado correctamente.",
                producto_fuente=producto_fuente,
                precio_fuente=precio_fuente,
                datos_originales=json.dumps({k: _valor_texto(v) for k, v in datos.items()}, ensure_ascii=True),
            )
        except Exception as exc:
            importacion.errores += 1
            DetalleImportacionProducto.objects.create(
                importacion=importacion,
                numero_fila=numero_fila,
                estado=DetalleImportacionProducto.ESTADO_ERROR,
                mensaje=f"No se pudo procesar la fila: {exc}",
                datos_originales=json.dumps({k: _valor_texto(v) for k, v in datos.items()}, ensure_ascii=True),
            )

    productos_canonicos = ProductoCanonico.objects.filter(pk__in=afectados)
    _recalcular_multifuente(productos_canonicos)

    importacion.estado = (
        ImportacionProductos.ESTADO_PROCESADA_CON_ERRORES
        if importacion.errores
        else ImportacionProductos.ESTADO_PROCESADA
    )
    importacion.fecha_procesamiento = timezone.now()
    importacion.save()
    return importacion


def crear_producto_desde_carga_url(datos):
    fila = {
        "titulo": datos["titulo"],
        "precio": datos["precio"],
        "url_producto": datos["url_producto"],
        "categoria": datos["categoria"].nombre,
        "marca": datos.get("marca"),
        "descripcion": datos.get("descripcion"),
        "imagen_url": datos.get("imagen_url"),
        "precio_lista": datos.get("precio_lista"),
        "costo_envio": datos.get("costo_envio"),
        "moneda": datos.get("moneda") or "ARS",
        "observaciones": datos.get("observaciones"),
        "origen_dato": PrecioFuente.ORIGEN_URL_ASISTIDA,
        "es_chico_liviano": datos.get("es_chico_liviano", False),
        "es_fragil": datos.get("es_fragil", False),
    }
    errores = validar_fila_producto(fila)
    if errores:
        return {"ok": False, "errores": errores}

    producto_canonico, _ = obtener_o_crear_producto_canonico(fila, datos["categoria"])
    producto_canonico.es_chico_liviano = bool(datos.get("es_chico_liviano"))
    producto_canonico.es_fragil = bool(datos.get("es_fragil"))
    producto_canonico.save(update_fields=["es_chico_liviano", "es_fragil", "fecha_actualizacion"])
    producto_fuente, _, _ = crear_o_actualizar_producto_fuente(
        fila,
        datos["fuente_web"],
        datos["categoria"],
        producto_canonico,
        actualizar=True,
    )
    precio_fuente, _ = crear_precio_fuente(producto_fuente, fila, crear_si_no_cambio=False)
    comparacion = calcular_comparacion_producto(producto_canonico)
    evaluacion = evaluar_producto_multifuente(producto_canonico)
    return {
        "ok": True,
        "producto_canonico": producto_canonico,
        "producto_fuente": producto_fuente,
        "precio_fuente": precio_fuente,
        "comparacion": comparacion,
        "evaluacion": evaluacion,
    }
