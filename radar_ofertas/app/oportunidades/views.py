from django.contrib import messages
from django.db.models import Count, Max, Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import (
    CargaProductoURLForm,
    ConfiguracionExtractorWebForm,
    ConectorCatalogoForm,
    ImportacionProductosForm,
    MercadoLibreBusquedaForm,
    OportunidadFiltroForm,
)
from .models import (
    AuditoriaFuenteWeb,
    CategoriaInteres,
    ConfiguracionExtractorWeb,
    ConsultaMercadoLibre,
    DecisionTecnica,
    DetalleImportacionProducto,
    EvaluacionOportunidadMultifuente,
    FuenteWeb,
    ImportacionProductos,
    MercadoLibreToken,
    Oportunidad,
    PrecioFuente,
    ProductoCanonico,
    ProductoFuente,
    ResultadoExtraccionWeb,
)
from .serializers import (
    CargaProductoURLSerializer,
    AuditoriaFuenteWebSerializer,
    ConectorFuenteSerializer,
    ConfiguracionExtractorWebSerializer,
    ContenidoSugeridoSerializer,
    ConsultaMercadoLibreSerializer,
    DecisionTecnicaSerializer,
    EjecucionConectorSerializer,
    FuenteWebSerializer,
    ImportacionProductosCreateSerializer,
    ImportacionProductosSerializer,
    MeliSincronizarSerializer,
    OportunidadDetalleSerializer,
    OportunidadEstadoSerializer,
    OportunidadSerializer,
    ProductoCanonicoSerializer,
    ProductoFuenteSerializer,
    ProductoMultifuenteSerializer,
    ResultadoExtraccionWebSerializer,
)
from oportunidades.management.commands.preparar_decohome import preparar_decohome
from .services.auditoria_fuentes_service import (
    actualizar_politica_desde_auditoria,
    auditar_fuente_basica,
    interpretar_auditoria,
)
from .services.clasificacion_service import clasificar_oportunidad
from .services.contenido_service import generar_contenido_basico
from .services.comparacion_service import calcular_comparacion_producto
from .services.evaluacion_multifuente_service import evaluar_producto_multifuente
from .services.importacion_service import (
    crear_producto_desde_carga_url,
    detectar_tipo_archivo,
    procesar_importacion,
)
from .models import ConectorFuente, EjecucionConector
from .services.conectores_service import validar_conector_segun_politica
from .services.conector_catalogo_service import ejecutar_conector_catalogo, validar_conector_catalogo
from .services.extractor_web_service import extraer_productos_preview, validar_ejecucion_extractor
from .services.storage_service import diagnosticar_storage_config
from .services.mercado_libre_service import (
    buscar_productos,
    diagnosticar_endpoints_meli,
    generar_url_autorizacion,
    get_meli_config,
    intercambiar_code_por_token,
    obtener_token_activo,
    preparar_link_afiliado,
    sincronizar_busqueda_meli,
)


def lista_oportunidades(request):
    form = OportunidadFiltroForm(request.GET or None)
    oportunidades = (
        Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente")
        .annotate(fecha_ultimo_precio=Max("producto__precios__fecha_relevamiento"))
        .all()
    )

    if form.is_valid():
        tipo = form.cleaned_data.get("tipo")
        estado = form.cleaned_data.get("estado")
        fuente = form.cleaned_data.get("fuente")
        categoria = form.cleaned_data.get("categoria")

        if tipo:
            oportunidades = oportunidades.filter(tipo=tipo)
        if estado:
            oportunidades = oportunidades.filter(estado=estado)
        if fuente:
            oportunidades = oportunidades.filter(producto__fuente_id=fuente)
        if categoria:
            oportunidades = oportunidades.filter(producto__categoria=categoria)

    return render(
        request,
        "oportunidades/lista_oportunidades.html",
        {
            "form": form,
            "oportunidades": oportunidades,
            "estados_accion": [
                ("revisado", "Revisado"),
                ("publicado", "Publicado"),
                ("comprado", "Comprado"),
                ("descartado", "Descartar"),
            ],
        },
    )


def detalle_oportunidad(request, pk):
    oportunidad = get_object_or_404(
        Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente").prefetch_related(
            "producto__precios",
            "contenidos",
            "publicaciones",
        ),
        pk=pk,
    )
    ultima_consulta_meli = ConsultaMercadoLibre.objects.filter(
        categoria=oportunidad.producto.categoria,
        exitosa=True,
    ).order_by("-fecha_consulta").first()
    return render(
        request,
        "oportunidades/detalle_oportunidad.html",
        {
            "oportunidad": oportunidad,
            "ultima_consulta_meli": ultima_consulta_meli,
            "link_afiliado": preparar_link_afiliado(oportunidad.producto),
        },
    )


def buscar_mercado_libre(request):
    form = MercadoLibreBusquedaForm(request.POST or None)
    resumen = None
    config = get_meli_config()

    if request.method == "POST" and form.is_valid():
        query = form.cleaned_data["query"]
        categoria = form.cleaned_data.get("categoria")
        limit = form.cleaned_data["limit"]
        offset = form.cleaned_data["offset"]
        usar_token_si_existe = form.cleaned_data["usar_token_si_existe"]
        resumen = sincronizar_busqueda_meli(
            query,
            categoria=categoria,
            limit=limit,
            offset=offset,
            usar_token_si_existe=usar_token_si_existe,
        )
        if resumen.get("forbidden"):
            messages.warning(
                request,
                "La consulta fue rechazada por Mercado Libre. Proba autorizar la aplicacion o configurar MELI_ACCESS_TOKEN.",
            )
        messages.success(
            request,
            (
                f"Busqueda procesada: {resumen['procesados']} productos, "
                f"{resumen['creados']} creados, {resumen['actualizados']} actualizados, "
                f"{resumen['errores']} errores."
            ),
        )

    return render(
        request,
        "oportunidades/buscar_mercado_libre.html",
        {
            "form": form,
            "resumen": resumen,
            "tiene_token": bool(obtener_token_activo()),
            "puede_autorizar": bool(config["client_id"] and config["redirect_uri"]),
        },
    )


def oauth_diagnostico(request):
    config = get_meli_config()
    token = MercadoLibreToken.objects.filter(activo=True).order_by("-fecha_actualizacion", "-id").first()
    return render(
        request,
        "oportunidades/diagnostico_mercado_libre.html",
        {
            "client_id_configurado": bool(config["client_id"]),
            "client_secret_configurado": bool(config["client_secret"]),
            "token_activo": bool(obtener_token_activo()),
            "token_db": token,
            "redirect_uri": config["redirect_uri"],
        },
    )


def diagnostico_endpoints_meli(request):
    query = request.GET.get("query") or "calza mujer"
    item_id = request.GET.get("item_id") or "MLA3092462776"
    limit = request.GET.get("limit") or 1

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 1

    diagnostico = diagnosticar_endpoints_meli(query=query, item_id=item_id, limit=limit)
    return render(
        request,
        "oportunidades/diagnostico_endpoints_meli.html",
        {
            "diagnostico": diagnostico,
        },
    )


def oauth_iniciar(request):
    resultado = generar_url_autorizacion()
    if not resultado["ok"]:
        messages.error(request, resultado["error"])
        return redirect("oportunidades:oauth_diagnostico")

    return redirect(resultado["url"])


def oauth_callback(request):
    code = request.GET.get("code")
    error = request.GET.get("error")

    if error:
        messages.error(request, f"Mercado Libre devolvio error OAuth: {error}")
        return redirect("oportunidades:buscar_meli")

    resultado = intercambiar_code_por_token(code)
    if resultado.get("ok"):
        messages.success(request, "Mercado Libre autorizado correctamente.")
    else:
        messages.error(request, resultado.get("error") or "No se pudo autorizar Mercado Libre.")

    return redirect("oportunidades:buscar_meli")


def lista_fuentes(request):
    fuentes = FuenteWeb.objects.select_related("politica_extraccion").all()
    return render(request, "oportunidades/lista_fuentes.html", {"fuentes": fuentes})


def detalle_fuente(request, pk):
    fuente = get_object_or_404(
        FuenteWeb.objects.select_related("politica_extraccion").prefetch_related(
            "categorias_fuente",
            "productos_fuente",
        ),
        pk=pk,
    )
    decisiones = DecisionTecnica.objects.filter(descripcion__icontains=fuente.nombre)[:10]
    return render(
        request,
        "oportunidades/detalle_fuente.html",
        {
            "fuente": fuente,
            "decisiones": decisiones,
        },
    )


def lista_auditorias_fuentes(request):
    auditorias = AuditoriaFuenteWeb.objects.select_related("fuente_web").all()
    return render(request, "oportunidades/lista_auditorias_fuentes.html", {"auditorias": auditorias})


def detalle_auditoria_fuente(request, pk):
    auditoria = get_object_or_404(AuditoriaFuenteWeb.objects.select_related("fuente_web").prefetch_related("recursos"), pk=pk)
    sugerencias = actualizar_politica_desde_auditoria(auditoria, aplicar=False)
    return render(
        request,
        "oportunidades/detalle_auditoria_fuente.html",
        {
            "auditoria": auditoria,
            "interpretacion": interpretar_auditoria(auditoria),
            "sugerencias": sugerencias,
        },
    )


@require_POST
def aplicar_politica_auditoria(request, pk):
    auditoria = get_object_or_404(AuditoriaFuenteWeb, pk=pk)
    actualizar_politica_desde_auditoria(auditoria, aplicar=True)
    messages.success(request, "Politica sugerida aplicada a la fuente.")
    return redirect("oportunidades:detalle_auditoria_fuente", pk=auditoria.pk)


@require_POST
def auditar_fuente_view(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    auditoria = auditar_fuente_basica(fuente)
    messages.success(request, "Auditoria de fuente finalizada.")
    return redirect("oportunidades:detalle_auditoria_fuente", pk=auditoria.pk)


def preparar_decohome_view(request):
    fuente, _ = preparar_decohome()
    messages.success(request, "Deco Home preparada como fuente candidata.")
    return redirect("oportunidades:detalle_fuente", pk=fuente.pk)


def auditar_decohome_view(request):
    fuente, _ = preparar_decohome()
    auditoria = auditar_fuente_basica(fuente)
    messages.success(request, "Auditoria inicial de Deco Home finalizada.")
    return redirect("oportunidades:detalle_auditoria_fuente", pk=auditoria.pk)


def politica_scraping(request):
    return render(request, "oportunidades/politica_scraping.html")


def lista_extractores(request):
    extractores = ConfiguracionExtractorWeb.objects.select_related("conector", "conector__fuente_web").all()
    datos = [(extractor, validar_ejecucion_extractor(extractor.conector)) for extractor in extractores]
    return render(request, "oportunidades/lista_extractores.html", {"datos_extractores": datos})


def detalle_extractor(request, pk):
    extractor = get_object_or_404(
        ConfiguracionExtractorWeb.objects.select_related(
            "conector",
            "conector__fuente_web",
            "conector__fuente_web__politica_extraccion",
        ),
        pk=pk,
    )
    ejecuciones = extractor.conector.ejecuciones.prefetch_related("resultados_web").all()[:10]
    resultados = ResultadoExtraccionWeb.objects.filter(ejecucion__conector=extractor.conector)[:20]
    return render(
        request,
        "oportunidades/detalle_extractor.html",
        {
            "extractor": extractor,
            "validacion": validar_ejecucion_extractor(extractor.conector),
            "ejecuciones": ejecuciones,
            "resultados": resultados,
        },
    )


def editar_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb, pk=pk)
    form = ConfiguracionExtractorWebForm(request.POST or None, instance=extractor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Configuracion de extractor actualizada.")
        return redirect("oportunidades:detalle_extractor", pk=extractor.pk)
    return render(request, "oportunidades/editar_extractor.html", {"form": form, "extractor": extractor})


@require_POST
def preview_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
    ejecucion = extraer_productos_preview(extractor.conector, procesar=False)
    if ejecucion.errores:
        messages.error(request, ejecucion.mensaje)
    else:
        messages.success(request, ejecucion.mensaje)
    return redirect("oportunidades:detalle_extractor", pk=extractor.pk)


@require_POST
def procesar_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
    ejecucion = extraer_productos_preview(extractor.conector, procesar=True)
    if ejecucion.errores:
        messages.error(request, ejecucion.mensaje)
    else:
        messages.success(request, ejecucion.mensaje)
    return redirect("oportunidades:detalle_extractor", pk=extractor.pk)


def lista_decisiones_tecnicas(request):
    decisiones = DecisionTecnica.objects.all()
    return render(request, "oportunidades/lista_decisiones_tecnicas.html", {"decisiones": decisiones})


def lista_importaciones(request):
    importaciones = ImportacionProductos.objects.select_related("fuente_web").all()
    return render(request, "oportunidades/lista_importaciones.html", {"importaciones": importaciones})


def nueva_importacion(request):
    form = ImportacionProductosForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        importacion = ImportacionProductos.objects.create(
            fuente_web=form.cleaned_data["fuente_web"],
            archivo=form.cleaned_data["archivo"],
            tipo_archivo=detectar_tipo_archivo(form.cleaned_data["archivo"]),
            observaciones=form.cleaned_data.get("observaciones"),
        )
        warning = form.get_warning()
        if warning:
            messages.warning(request, warning)
        procesar_importacion(
            importacion,
            {
                "categoria_default": form.cleaned_data.get("categoria_default"),
                "origen_dato": form.cleaned_data.get("origen_dato"),
                "crear_producto_canonico": form.cleaned_data.get("crear_producto_canonico"),
                "actualizar_productos_existentes": form.cleaned_data.get("actualizar_productos_existentes"),
                "crear_precio_si_no_cambio": form.cleaned_data.get("crear_precio_si_no_cambio"),
            },
        )
        messages.success(request, "Importacion procesada.")
        return redirect("oportunidades:detalle_importacion", pk=importacion.pk)

    return render(request, "oportunidades/nueva_importacion.html", {"form": form})


def descargar_plantilla_importacion(request):
    contenido = (
        "codigo_externo,titulo,precio,precio_lista,descuento_porcentaje,costo_envio,moneda,"
        "url_producto,categoria,marca,descripcion,imagen_url,vendedor,condicion,disponible,stock\n"
        "SKU-001,Organizador de cocina extensible,\"1200,50\",1500,20,0,ARS,"
        "https://ejemplo.com/producto/sku-001,Organizacion,Marca Demo,"
        "Organizador plastico para cocina,https://ejemplo.com/imagen.jpg,"
        "Proveedor Demo,nuevo,si,Disponible\n"
    )
    response = HttpResponse(contenido, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="productos_template.csv"'
    return response


def detalle_importacion(request, pk):
    importacion = get_object_or_404(ImportacionProductos.objects.select_related("fuente_web"), pk=pk)
    detalles = importacion.detalles.select_related("producto_fuente", "precio_fuente").all()
    return render(
        request,
        "oportunidades/detalle_importacion.html",
        {
            "importacion": importacion,
            "detalles": detalles,
        },
    )


@require_POST
def procesar_importacion_view(request, pk):
    importacion = get_object_or_404(ImportacionProductos, pk=pk)
    if importacion.estado == ImportacionProductos.ESTADO_PROCESANDO:
        messages.warning(request, "La importacion ya esta en proceso.")
    else:
        procesar_importacion(importacion)
        messages.success(request, "Importacion procesada correctamente.")
    return redirect("oportunidades:detalle_importacion", pk=importacion.pk)


def cargar_producto_url(request):
    form = CargaProductoURLForm(request.POST or None)
    resultado = None
    if request.method == "POST" and form.is_valid():
        resultado = crear_producto_desde_carga_url(form.cleaned_data)
        if resultado["ok"]:
            messages.success(request, "Producto cargado por URL sin descargar la pagina.")
            return redirect("oportunidades:detalle_producto_multifuente", pk=resultado["producto_canonico"].pk)
        messages.error(request, "No se pudo cargar el producto: " + " ".join(resultado["errores"]))
    return render(request, "oportunidades/cargar_producto_url.html", {"form": form, "resultado": resultado})


def lista_productos_multifuente(request):
    productos = (
        ProductoCanonico.objects.select_related("categoria")
        .prefetch_related("comparaciones", "evaluaciones_multifuente", "apariciones")
        .annotate(cantidad_apariciones=Count("apariciones", distinct=True))
        .all()
    )
    return render(request, "oportunidades/lista_productos_multifuente.html", {"productos": productos})


def detalle_producto_multifuente(request, pk):
    producto = get_object_or_404(
        ProductoCanonico.objects.select_related("categoria").prefetch_related(
            Prefetch("apariciones", queryset=ProductoFuente.objects.select_related("fuente_web", "categoria_fuente")),
            "apariciones__precios_fuente",
            "comparaciones",
            "evaluaciones_multifuente",
        ),
        pk=pk,
    )
    return render(request, "oportunidades/detalle_producto_multifuente.html", {"producto": producto})


def diagnostico_storage(request):
    diagnostico = diagnosticar_storage_config()
    return render(request, "oportunidades/diagnostico_storage.html", {"diagnostico": diagnostico})


def lista_conectores(request):
    conectores = ConectorFuente.objects.select_related("fuente_web", "fuente_web__politica_extraccion").all()
    datos = [(conector, validar_conector_segun_politica(conector)) for conector in conectores]
    return render(request, "oportunidades/lista_conectores.html", {"datos_conectores": datos})


def nuevo_conector_catalogo(request):
    form = ConectorCatalogoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        tipo = form.cleaned_data["tipo_conector"]
        conector = ConectorFuente.objects.create(
            fuente_web=form.cleaned_data["fuente_web"],
            nombre=form.cleaned_data["nombre"],
            tipo_conector=tipo,
            estado=ConectorFuente.ESTADO_ACTIVO,
            url_recurso=form.cleaned_data.get("url_recurso") or None,
            formato_recurso=form.cleaned_data.get("formato_recurso") or ConectorFuente.FORMATO_DESCONOCIDO,
            requiere_descarga=tipo in {ConectorFuente.TIPO_CSV_REMOTO, ConectorFuente.TIPO_EXCEL_REMOTO},
            fuente_autorizo_uso=form.cleaned_data.get("fuente_autorizo_uso", False),
            frecuencia_sugerida=form.cleaned_data.get("frecuencia_sugerida") or None,
            descripcion=form.cleaned_data.get("descripcion") or None,
            notas_uso_datos=form.cleaned_data.get("notas_uso_datos") or None,
        )
        validacion = validar_conector_catalogo(conector)
        if validacion["nivel"] == "bloqueado":
            conector.estado = ConectorFuente.ESTADO_BORRADOR
            conector.save(update_fields=["estado"])
            messages.error(request, validacion["mensaje"])
        else:
            messages.success(request, "Conector catalogo creado correctamente.")
        return redirect("oportunidades:detalle_conector", pk=conector.pk)
    return render(request, "oportunidades/nuevo_conector_catalogo.html", {"form": form})


def detalle_conector(request, pk):
    conector = get_object_or_404(
        ConectorFuente.objects.select_related("fuente_web", "fuente_web__politica_extraccion").prefetch_related(
            "ejecuciones",
            "importaciones",
        ),
        pk=pk,
    )
    return render(
        request,
        "oportunidades/detalle_conector.html",
        {
            "conector": conector,
            "validacion": validar_conector_catalogo(conector)
            if conector.tipo_conector in {
                ConectorFuente.TIPO_CSV_MANUAL,
                ConectorFuente.TIPO_EXCEL_MANUAL,
                ConectorFuente.TIPO_CSV_REMOTO,
                ConectorFuente.TIPO_EXCEL_REMOTO,
            }
            else validar_conector_segun_politica(conector),
            "ejecuciones": conector.ejecuciones.all()[:20],
            "importaciones": conector.importaciones.all()[:20],
        },
    )


@require_POST
def validar_conector(request, pk):
    conector = get_object_or_404(ConectorFuente.objects.select_related("fuente_web", "fuente_web__politica_extraccion"), pk=pk)
    validacion = validar_conector_segun_politica(conector)
    level = messages.success if validacion["nivel"] == "ok" else messages.warning
    if validacion["nivel"] == "bloqueado":
        level = messages.error
    level(request, validacion["mensaje"])
    return redirect("oportunidades:detalle_conector", pk=conector.pk)


@require_POST
def ejecutar_conector(request, pk):
    conector = get_object_or_404(ConectorFuente.objects.select_related("fuente_web", "fuente_web__politica_extraccion"), pk=pk)
    if conector.tipo_conector not in {
        ConectorFuente.TIPO_CSV_MANUAL,
        ConectorFuente.TIPO_EXCEL_MANUAL,
        ConectorFuente.TIPO_CSV_REMOTO,
        ConectorFuente.TIPO_EXCEL_REMOTO,
    }:
        messages.error(request, "Este tipo de conector todavia no tiene ejecucion operativa.")
        return redirect("oportunidades:detalle_conector", pk=conector.pk)
    ejecucion = ejecutar_conector_catalogo(conector)
    if ejecucion.estado == EjecucionConector.ESTADO_ERROR:
        messages.error(request, ejecucion.mensaje or "El conector finalizo con error.")
    elif ejecucion.estado == EjecucionConector.ESTADO_FINALIZADA_CON_ERRORES:
        messages.warning(request, ejecucion.mensaje or "El conector finalizo con errores.")
    else:
        messages.success(request, ejecucion.mensaje or "Conector ejecutado correctamente.")
    return redirect("oportunidades:detalle_conector", pk=conector.pk)


@require_POST
def recalcular_comparacion_multifuente(request, pk):
    producto = get_object_or_404(ProductoCanonico, pk=pk)
    calcular_comparacion_producto(producto)
    messages.success(request, "Comparacion recalculada.")
    return redirect("oportunidades:detalle_producto_multifuente", pk=producto.pk)


@require_POST
def recalcular_evaluacion_multifuente(request, pk):
    producto = get_object_or_404(ProductoCanonico, pk=pk)
    evaluar_producto_multifuente(producto)
    messages.success(request, "Evaluacion recalculada.")
    return redirect("oportunidades:detalle_producto_multifuente", pk=producto.pk)


def _recalcular_oportunidad(oportunidad):
    evaluacion = clasificar_oportunidad(
        oportunidad.producto,
        oportunidad.precio_actual,
        precio_reventa_estimado=oportunidad.precio_reventa_estimado or None,
    )
    oportunidad.precio_reventa_estimado = evaluacion["precio_reventa_estimado"]
    oportunidad.margen_estimado = evaluacion["margen_estimado"]
    oportunidad.porcentaje_margen = evaluacion["porcentaje_margen"]
    oportunidad.tipo = evaluacion["tipo"]
    oportunidad.riesgo = evaluacion["riesgo"]
    oportunidad.puntaje = evaluacion["puntaje"]
    oportunidad.motivo = evaluacion["motivo"]
    oportunidad.save(
        update_fields=[
            "precio_reventa_estimado",
            "margen_estimado",
            "porcentaje_margen",
            "tipo",
            "riesgo",
            "puntaje",
            "motivo",
        ]
    )
    return oportunidad


def _generar_o_actualizar_contenido(oportunidad):
    datos = generar_contenido_basico(oportunidad)
    contenido = oportunidad.contenidos.order_by("-fecha_creacion", "-id").first()

    if contenido:
        for campo, valor in datos.items():
            setattr(contenido, campo, valor)
        contenido.generado_con_ia = False
        contenido.save(update_fields=["gancho", "guion_corto", "descripcion", "hashtags", "generado_con_ia"])
        creado = False
    else:
        contenido = oportunidad.contenidos.create(**datos, generado_con_ia=False)
        creado = True

    return contenido, creado


@require_POST
def cambiar_estado_oportunidad(request, pk, nuevo_estado):
    oportunidad = get_object_or_404(Oportunidad, pk=pk)
    estados_validos = dict(Oportunidad.ESTADO_CHOICES)

    if nuevo_estado not in estados_validos:
        messages.error(request, "Estado invalido.")
        return redirect("oportunidades:lista")

    oportunidad.estado = nuevo_estado
    oportunidad.save(update_fields=["estado"])
    messages.success(request, f"Oportunidad marcada como {estados_validos[nuevo_estado].lower()}.")
    return redirect(request.POST.get("next") or "oportunidades:lista")


@require_POST
def recalcular_oportunidad(request, pk):
    oportunidad = get_object_or_404(
        Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente"),
        pk=pk,
    )
    _recalcular_oportunidad(oportunidad)
    messages.success(request, "Oportunidad recalculada correctamente.")
    next_url = request.POST.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("oportunidades:detalle", pk=oportunidad.pk)


@require_POST
def generar_contenido_oportunidad(request, pk):
    oportunidad = get_object_or_404(
        Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente"),
        pk=pk,
    )
    _generar_o_actualizar_contenido(oportunidad)
    messages.success(request, "Contenido basico generado correctamente.")
    return redirect("oportunidades:detalle", pk=oportunidad.pk)


class OportunidadListAPIView(generics.ListAPIView):
    queryset = Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente")
    serializer_class = OportunidadSerializer


class OportunidadDetailAPIView(generics.RetrieveAPIView):
    queryset = Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente").prefetch_related(
        "contenidos",
        "publicaciones",
    )
    serializer_class = OportunidadDetalleSerializer


class OportunidadEstadoAPIView(APIView):
    def patch(self, request, pk):
        oportunidad = get_object_or_404(Oportunidad, pk=pk)
        serializer = OportunidadEstadoSerializer(oportunidad, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class OportunidadRecalcularAPIView(APIView):
    def post(self, request, pk):
        oportunidad = get_object_or_404(
            Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente"),
            pk=pk,
        )
        oportunidad = _recalcular_oportunidad(oportunidad)
        serializer = OportunidadSerializer(oportunidad)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OportunidadGenerarContenidoAPIView(APIView):
    def post(self, request, pk):
        oportunidad = get_object_or_404(
            Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente"),
            pk=pk,
        )
        contenido, creado = _generar_o_actualizar_contenido(oportunidad)
        serializer = ContenidoSugeridoSerializer(contenido)
        response_status = status.HTTP_201_CREATED if creado else status.HTTP_200_OK
        return Response(serializer.data, status=response_status)


class MeliBuscarAPIView(APIView):
    def get(self, request):
        query = request.query_params.get("q") or request.query_params.get("query")
        limit = request.query_params.get("limit", 10)
        offset = request.query_params.get("offset", 0)

        if not query:
            return Response({"detail": "Parametro q requerido."}, status=status.HTTP_400_BAD_REQUEST)

        respuesta = buscar_productos(query, limit=limit, offset=offset)
        response_status = status.HTTP_200_OK if respuesta.get("ok") else status.HTTP_502_BAD_GATEWAY
        return Response(respuesta, status=response_status)


class MeliSincronizarAPIView(APIView):
    def post(self, request):
        serializer = MeliSincronizarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        categoria = None
        query = data.get("query")

        categoria_id = data.get("categoria_id")
        if categoria_id:
            categoria = get_object_or_404(CategoriaInteres, pk=categoria_id)
            query = query or categoria.palabra_clave

        resumen = sincronizar_busqueda_meli(
            query,
            categoria=categoria,
            limit=data.get("limit", 20),
            offset=data.get("offset", 0),
            usar_token_si_existe=data.get("usar_token_si_existe", True),
        )
        return Response(resumen, status=status.HTTP_200_OK)


class MeliConsultasAPIView(generics.ListAPIView):
    queryset = ConsultaMercadoLibre.objects.select_related("categoria").all()
    serializer_class = ConsultaMercadoLibreSerializer


class FuenteWebListAPIView(generics.ListAPIView):
    queryset = FuenteWeb.objects.select_related("politica_extraccion").all()
    serializer_class = FuenteWebSerializer


class FuenteWebDetailAPIView(generics.RetrieveAPIView):
    queryset = FuenteWeb.objects.select_related("politica_extraccion").all()
    serializer_class = FuenteWebSerializer


class DecisionTecnicaListAPIView(generics.ListAPIView):
    queryset = DecisionTecnica.objects.all()
    serializer_class = DecisionTecnicaSerializer


class ProductoCanonicoListAPIView(generics.ListAPIView):
    queryset = ProductoCanonico.objects.select_related("categoria").all()
    serializer_class = ProductoCanonicoSerializer


class ProductoFuenteListAPIView(generics.ListAPIView):
    queryset = ProductoFuente.objects.select_related("fuente_web", "categoria_fuente", "producto_canonico").all()
    serializer_class = ProductoFuenteSerializer


class ConectorFuenteListAPIView(generics.ListAPIView):
    queryset = ConectorFuente.objects.select_related("fuente_web", "fuente_web__politica_extraccion").all()
    serializer_class = ConectorFuenteSerializer


class ConectorFuenteDetailAPIView(generics.RetrieveAPIView):
    queryset = ConectorFuente.objects.select_related("fuente_web", "fuente_web__politica_extraccion").all()
    serializer_class = ConectorFuenteSerializer


class ConectorFuenteValidarAPIView(APIView):
    def post(self, request, pk):
        conector = get_object_or_404(
            ConectorFuente.objects.select_related("fuente_web", "fuente_web__politica_extraccion"),
            pk=pk,
        )
        return Response(validar_conector_segun_politica(conector), status=status.HTTP_200_OK)


class ConectorFuenteEjecutarAPIView(APIView):
    def post(self, request, pk):
        conector = get_object_or_404(
            ConectorFuente.objects.select_related("fuente_web", "fuente_web__politica_extraccion"),
            pk=pk,
        )
        ejecucion = ejecutar_conector_catalogo(conector)
        return Response(EjecucionConectorSerializer(ejecucion).data, status=status.HTTP_200_OK)


class ConectorCatalogoCreateAPIView(APIView):
    def post(self, request):
        fuente = get_object_or_404(FuenteWeb, pk=request.data.get("fuente_web"))
        tipo = request.data.get("tipo_conector")
        if tipo not in {
            ConectorFuente.TIPO_CSV_MANUAL,
            ConectorFuente.TIPO_EXCEL_MANUAL,
            ConectorFuente.TIPO_CSV_REMOTO,
            ConectorFuente.TIPO_EXCEL_REMOTO,
        }:
            return Response({"detail": "tipo_conector no valido para catalogo."}, status=status.HTTP_400_BAD_REQUEST)
        conector = ConectorFuente.objects.create(
            fuente_web=fuente,
            nombre=request.data.get("nombre") or "Conector catalogo",
            tipo_conector=tipo,
            estado=ConectorFuente.ESTADO_ACTIVO,
            url_recurso=request.data.get("url_recurso") or None,
            formato_recurso=request.data.get("formato_recurso") or ConectorFuente.FORMATO_DESCONOCIDO,
            requiere_descarga=tipo in {ConectorFuente.TIPO_CSV_REMOTO, ConectorFuente.TIPO_EXCEL_REMOTO},
            fuente_autorizo_uso=bool(request.data.get("fuente_autorizo_uso", False)),
            descripcion=request.data.get("descripcion") or None,
            notas_uso_datos=request.data.get("notas_uso_datos") or None,
        )
        validacion = validar_conector_catalogo(conector)
        if validacion["nivel"] == "bloqueado":
            conector.estado = ConectorFuente.ESTADO_BORRADOR
            conector.save(update_fields=["estado"])
            return Response({"validacion": validacion}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ConectorFuenteSerializer(conector).data, status=status.HTTP_201_CREATED)


class EjecucionConectorListAPIView(generics.ListAPIView):
    queryset = EjecucionConector.objects.select_related("conector", "conector__fuente_web").all()
    serializer_class = EjecucionConectorSerializer


class EjecucionConectorDetailAPIView(generics.RetrieveAPIView):
    queryset = EjecucionConector.objects.select_related("conector", "conector__fuente_web").prefetch_related("detalles")
    serializer_class = EjecucionConectorSerializer


class AuditoriaFuenteWebListAPIView(generics.ListAPIView):
    queryset = AuditoriaFuenteWeb.objects.select_related("fuente_web").prefetch_related("recursos").all()
    serializer_class = AuditoriaFuenteWebSerializer


class AuditoriaFuenteWebDetailAPIView(generics.RetrieveAPIView):
    queryset = AuditoriaFuenteWeb.objects.select_related("fuente_web").prefetch_related("recursos").all()
    serializer_class = AuditoriaFuenteWebSerializer


class FuenteAuditarAPIView(APIView):
    def post(self, request, pk):
        fuente = get_object_or_404(FuenteWeb, pk=pk)
        auditoria = auditar_fuente_basica(fuente)
        return Response(AuditoriaFuenteWebSerializer(auditoria).data, status=status.HTTP_201_CREATED)


class DecoHomePrepararAPIView(APIView):
    def post(self, request):
        fuente, _ = preparar_decohome()
        return Response(FuenteWebSerializer(fuente).data, status=status.HTTP_200_OK)


class DecoHomeAuditarAPIView(APIView):
    def post(self, request):
        fuente, _ = preparar_decohome()
        auditoria = auditar_fuente_basica(fuente)
        return Response(AuditoriaFuenteWebSerializer(auditoria).data, status=status.HTTP_201_CREATED)


class ConfiguracionExtractorWebListAPIView(generics.ListAPIView):
    queryset = ConfiguracionExtractorWeb.objects.select_related("conector", "conector__fuente_web").all()
    serializer_class = ConfiguracionExtractorWebSerializer


class ConfiguracionExtractorWebDetailAPIView(generics.RetrieveAPIView):
    queryset = ConfiguracionExtractorWeb.objects.select_related("conector", "conector__fuente_web").all()
    serializer_class = ConfiguracionExtractorWebSerializer


class ExtractorPreviewAPIView(APIView):
    def post(self, request, pk):
        extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
        ejecucion = extraer_productos_preview(extractor.conector, procesar=False)
        return Response(EjecucionConectorSerializer(ejecucion).data, status=status.HTTP_200_OK)


class ExtractorProcesarAPIView(APIView):
    def post(self, request, pk):
        extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
        ejecucion = extraer_productos_preview(extractor.conector, procesar=True)
        return Response(EjecucionConectorSerializer(ejecucion).data, status=status.HTTP_200_OK)


class ImportacionProductosListCreateAPIView(generics.ListCreateAPIView):
    queryset = ImportacionProductos.objects.select_related("fuente_web").prefetch_related("detalles").all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ImportacionProductosCreateSerializer
        return ImportacionProductosSerializer

    def perform_create(self, serializer):
        archivo = serializer.validated_data["archivo"]
        serializer.save(tipo_archivo=detectar_tipo_archivo(archivo))


class ImportacionProductosDetailAPIView(generics.RetrieveAPIView):
    queryset = ImportacionProductos.objects.select_related("fuente_web").prefetch_related("detalles").all()
    serializer_class = ImportacionProductosSerializer


class ImportacionProductosProcesarAPIView(APIView):
    def post(self, request, pk):
        importacion = get_object_or_404(ImportacionProductos, pk=pk)
        procesar_importacion(importacion)
        serializer = ImportacionProductosSerializer(importacion)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductoMultifuenteListAPIView(generics.ListAPIView):
    queryset = ProductoCanonico.objects.select_related("categoria").prefetch_related(
        "comparaciones",
        "evaluaciones_multifuente",
    )
    serializer_class = ProductoMultifuenteSerializer


class ProductoMultifuenteDetailAPIView(generics.RetrieveAPIView):
    queryset = ProductoCanonico.objects.select_related("categoria").prefetch_related(
        "apariciones",
        "apariciones__precios_fuente",
        "comparaciones",
        "evaluaciones_multifuente",
    )
    serializer_class = ProductoCanonicoSerializer


class CargaProductoURLAPIView(APIView):
    def post(self, request):
        serializer = CargaProductoURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resultado = crear_producto_desde_carga_url(serializer.validated_data)
        if not resultado["ok"]:
            return Response({"errores": resultado["errores"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "producto_canonico_id": resultado["producto_canonico"].pk,
                "producto_fuente_id": resultado["producto_fuente"].pk,
                "precio_fuente_id": resultado["precio_fuente"].pk if resultado["precio_fuente"] else None,
                "evaluacion_id": resultado["evaluacion"].pk if resultado["evaluacion"] else None,
            },
            status=status.HTTP_201_CREATED,
        )
