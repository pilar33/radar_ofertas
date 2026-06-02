import json
from urllib.parse import urlparse

from django.contrib import messages
from django.db.models import Count, Max, Prefetch, Q
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
    FuenteRapidaPreviewForm,
    FuenteWizardForm,
    ImportacionProductosForm,
    LaboratorioMapeoForm,
    LaboratorioSelectoresForm,
    MercadoLibreBusquedaForm,
    OportunidadFiltroForm,
    RevisionManualFuenteForm,
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
    OperacionCuraduria,
    PrecioFuente,
    ProductoCanonico,
    ProductoFuente,
    RevisionManualFuente,
    ResultadoExtraccionWeb,
    ResultadoLaboratorioMapeo,
    SesionLaboratorioMapeo,
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
    SesionLaboratorioMapeoSerializer,
    RevisionManualFuenteSerializer,
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
from .services.laboratorio_mapeo_service import (
    analizar_url_laboratorio,
    crear_sesion_laboratorio,
    guardar_laboratorio_como_extractor,
    procesar_resultados_laboratorio,
    probar_selectores_laboratorio,
)
from .models import ConectorFuente, EjecucionConector
from .services.conectores_service import validar_conector_segun_politica
from .services.conector_catalogo_service import ejecutar_conector_catalogo, validar_conector_catalogo
from .services.extractor_web_service import (
    extraer_productos_preview,
    obtener_condiciones_faltantes_extractor,
    validar_ejecucion_extractor,
)
from .services.revision_fuentes_service import aplicar_revision_a_politica
from .services.selector_preview_service import probar_url_preview
from .services.procesamiento_preview_service import (
    marcar_resultado_seleccionado,
    procesar_resultados_seleccionados,
    validar_resultado_procesable,
)
from .services.estado_fuente_service import evaluar_estado_operativo_fuente
from .services.headless_diagnostic_service import comparar_html_requests_vs_headless, diagnosticar_requiere_headless
from .services.ranking_preview_service import rankear_resultados_ejecucion
from .services.wizard_fuentes_service import crear_fuente_preview_rapida, crear_fuente_wizard, preparar_fuente_generica
from .services.storage_service import diagnosticar_storage_config
from .services.backup_service import exportar_snapshot_json, snapshot_resumen_json
from .services.curaduria_service import (
    crear_producto_canonico_desde_fuente,
    detectar_producto_fuente_duplicados,
    marcar_requiere_revision,
    marcar_revisado,
    reasignar_producto_canonico,
)
from .services.dataset_export_service import (
    exportar_dataset_completo_zip,
    exportar_dataset_productos_csv,
    exportar_historial_precios_csv,
    exportar_resultados_preview_csv,
)
from .services.entorno_service import obtener_advertencia_persistencia
from .services.ranking_comercial_service import calcular_score_comercial_producto_fuente, recalcular_ranking_comercial
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


def wizard_nueva_fuente(request):
    form = FuenteWizardForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        fuente, _ = crear_fuente_wizard(form.cleaned_data)
        messages.success(request, "Fuente creada con politica inicial pendiente de revision.")
        return redirect("oportunidades:wizard_auditoria_fuente", pk=fuente.pk)
    return render(request, "oportunidades/wizard_nueva_fuente.html", {"form": form})


def estado_operativo_fuentes(request):
    fuentes = FuenteWeb.objects.prefetch_related("conectores").all()
    estados = [(fuente, evaluar_estado_operativo_fuente(fuente)) for fuente in fuentes]
    return render(request, "oportunidades/lista_estado_fuentes.html", {"estados": estados})


def preparar_gangahome_view(request):
    contexto = {"preparada": False}
    if request.method == "POST":
        url_base = (request.POST.get("url_base") or "").strip()
        rubro = (request.POST.get("rubro") or "hogar/deco").strip()
        if not url_base:
            messages.error(request, "Indicar URL base de GangaHome.")
        else:
            try:
                fuente, conector, creada, conector_creado = preparar_fuente_generica("GangaHome", url_base, rubro)
                messages.success(request, "GangaHome preparada como fuente candidata.")
                return redirect("oportunidades:detalle_fuente", pk=fuente.pk)
            except ValueError as exc:
                messages.error(request, str(exc))
    return render(request, "oportunidades/preparar_gangahome.html", contexto)


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


def wizard_auditoria_fuente(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    auditoria = fuente.auditorias.first()
    return render(request, "oportunidades/wizard_auditoria_fuente.html", {"fuente": fuente, "auditoria": auditoria})


def wizard_revision_fuente(request, pk):
    return nueva_revision_fuente(request, pk)


def wizard_conector_fuente(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    conector, _ = ConectorFuente.objects.get_or_create(
        fuente_web=fuente,
        nombre=f"{fuente.nombre} - Conector web pendiente",
        defaults={
            "tipo_conector": ConectorFuente.TIPO_SCRAPING_PERMITIDO,
            "estado": ConectorFuente.ESTADO_BORRADOR,
            "requiere_revision_manual": True,
            "respeta_politica_fuente": False,
        },
    )
    messages.success(request, "Conector base creado en borrador.")
    return redirect("oportunidades:detalle_conector", pk=conector.pk)


def wizard_extractor_fuente(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    conector = fuente.conectores.filter(tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO).first()
    if not conector:
        messages.warning(request, "Primero crea el conector del wizard.")
        return redirect("oportunidades:wizard_conector_fuente", pk=fuente.pk)
    extractor, _ = ConfiguracionExtractorWeb.objects.get_or_create(
        conector=conector,
        defaults={
            "url_inicio": fuente.url_base,
            "pagina_prueba_url": fuente.url_base,
            "dominio_permitido": urlparse(fuente.url_base).netloc,
            "modo_extraccion": ConfiguracionExtractorWeb.MODO_PREVIEW_MANUAL,
            "habilitado": False,
            "solo_preview": True,
        },
    )
    return redirect("oportunidades:selectores_extractor", pk=extractor.pk)


def wizard_preview_fuente(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    extractor = ConfiguracionExtractorWeb.objects.filter(conector__fuente_web=fuente).first()
    if not extractor:
        messages.warning(request, "Primero configura el extractor.")
        return redirect("oportunidades:wizard_extractor_fuente", pk=fuente.pk)
    return redirect("oportunidades:detalle_extractor", pk=extractor.pk)


def wizard_procesar_fuente(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    extractor = ConfiguracionExtractorWeb.objects.filter(conector__fuente_web=fuente).first()
    if not extractor:
        messages.warning(request, "No hay extractor configurado.")
        return redirect("oportunidades:detalle_fuente", pk=fuente.pk)
    return redirect("oportunidades:resultados_extractor", pk=extractor.pk)


def lista_revisiones_fuente(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    revisiones = fuente.revisiones_manuales.all()
    return render(
        request,
        "oportunidades/lista_revisiones_fuente.html",
        {"fuente": fuente, "revisiones": revisiones},
    )


def nueva_revision_fuente(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    form = RevisionManualFuenteForm(request.POST or None, initial={"fuente_web": fuente})
    form.fields["fuente_web"].queryset = FuenteWeb.objects.filter(pk=fuente.pk)
    if request.method == "POST" and form.is_valid():
        revision = form.save(commit=False)
        revision.fuente_web = fuente
        revision.save()
        if revision.aplicar_a_politica:
            aplicar_revision_a_politica(revision)
            messages.success(request, "Revision registrada y aplicada a la politica.")
        else:
            messages.success(request, "Revision registrada sin modificar la politica.")
        return redirect("oportunidades:lista_revisiones_fuente", pk=fuente.pk)
    return render(
        request,
        "oportunidades/nueva_revision_fuente.html",
        {"fuente": fuente, "form": form},
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


def laboratorio_mapeo_web(request, fuente_id=None):
    fuente = FuenteWeb.objects.filter(pk=fuente_id).first() if fuente_id else None
    initial = {"fuente_web": fuente.pk} if fuente else {}
    form = LaboratorioMapeoForm(request.POST or None, initial=initial)
    sesion = None
    resultado = None
    if request.method == "POST" and form.is_valid():
        fuente = form.cleaned_data.get("fuente_web")
        resultado = analizar_url_laboratorio(
            form.cleaned_data["url"],
            limite=form.cleaned_data["limite"],
            modo=form.cleaned_data["modo"],
        )
        sesion = crear_sesion_laboratorio(resultado, fuente_web=fuente)
        if resultado["ok"]:
            messages.success(request, resultado["mensaje"])
        else:
            messages.warning(request, resultado["mensaje"])
    return render(
        request,
        "oportunidades/laboratorio_mapeo_web.html",
        {"form": form, "sesion": sesion, "resultado": resultado},
    )


def nueva_fuente_rapida(request):
    form = FuenteRapidaPreviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        fuente, conector, extractor, creada, _, plataforma = crear_fuente_preview_rapida(form.cleaned_data)
        messages.success(
            request,
            f"Fuente {'creada' if creada else 'actualizada'} y extractor preview habilitado. Plataforma: {plataforma}.",
        )
        return redirect("oportunidades:detalle_extractor", pk=extractor.pk)
    return render(request, "oportunidades/nueva_fuente_rapida.html", {"form": form})


def laboratorio_decohome(request):
    fuente = FuenteWeb.objects.filter(nombre="Deco Home").first()
    if not fuente:
        messages.warning(request, "Primero prepara Deco Home.")
        return redirect("oportunidades:preparar_decohome")
    return laboratorio_mapeo_web(request, fuente_id=fuente.pk)


def laboratorio_ayuda(request):
    return render(request, "oportunidades/laboratorio_ayuda.html")


def laboratorio_ajustar(request):
    sesion = SesionLaboratorioMapeo.objects.filter(pk=request.GET.get("sesion") or request.POST.get("sesion_id")).first()
    initial = {}
    if sesion:
        initial = {"url": sesion.url, "sesion_id": sesion.pk}
        try:
            initial.update(json.loads(sesion.selectores_sugeridos or "{}"))
        except json.JSONDecodeError:
            pass
    form = LaboratorioSelectoresForm(request.POST or None, initial=initial)
    resultado = None
    if request.method == "POST" and form.is_valid():
        selectores = {
            "product_card_selector": form.cleaned_data.get("product_card_selector"),
            "title_selector": form.cleaned_data.get("title_selector"),
            "price_selector": form.cleaned_data.get("price_selector"),
            "url_selector": form.cleaned_data.get("url_selector"),
            "image_selector": form.cleaned_data.get("image_selector"),
            "description_selector": form.cleaned_data.get("description_selector"),
        }
        analisis = analizar_url_laboratorio(form.cleaned_data["url"], limite=10, modo="css_selectors", selectores=selectores)
        resultado = analisis
        if sesion:
            sesion.selectores_sugeridos = json.dumps(selectores, ensure_ascii=True)
            sesion.save(update_fields=["selectores_sugeridos"])
        if analisis["productos_detectados"]:
            messages.success(request, f"Selectores probados: {len(analisis['productos_detectados'])} productos detectados.")
        else:
            messages.warning(request, "El selector no encontro elementos. Revisa el HTML o puede requerir JavaScript.")
    return render(request, "oportunidades/laboratorio_ajustar.html", {"form": form, "sesion": sesion, "resultado": resultado})


@require_POST
def laboratorio_guardar_extractor(request, sesion_id):
    sesion = get_object_or_404(SesionLaboratorioMapeo, pk=sesion_id)
    fuente = sesion.fuente_web or FuenteWeb.objects.filter(pk=request.POST.get("fuente_web")).first()
    extractor = guardar_laboratorio_como_extractor(
        sesion,
        fuente_web=fuente,
        nombre_fuente=request.POST.get("nombre_fuente", ""),
        rubro=request.POST.get("rubro", ""),
    )
    messages.success(
        request,
        "Extractor guardado. Puede requerir auditoria/revision antes de ejecutarse automaticamente.",
    )
    return redirect("oportunidades:detalle_extractor", pk=extractor.pk)


@require_POST
def laboratorio_seleccionar_resultado(request, resultado_id):
    resultado = get_object_or_404(ResultadoLaboratorioMapeo, pk=resultado_id)
    resultado.seleccionado = request.POST.get("seleccionado") != "0"
    resultado.save(update_fields=["seleccionado"])
    return redirect("oportunidades:laboratorio_sesion", sesion_id=resultado.sesion_id)


def laboratorio_sesion(request, sesion_id):
    sesion = get_object_or_404(SesionLaboratorioMapeo.objects.prefetch_related("resultados"), pk=sesion_id)
    return render(request, "oportunidades/laboratorio_sesion.html", {"sesion": sesion})


@require_POST
def laboratorio_procesar_seleccionados(request, sesion_id):
    sesion = get_object_or_404(SesionLaboratorioMapeo, pk=sesion_id)
    resumen = procesar_resultados_laboratorio(sesion, limite=10)
    if resumen["ok"]:
        messages.success(request, f"Procesados={resumen['procesados']}, precios={resumen.get('precios_creados', 0)}.")
    else:
        messages.error(request, resumen["mensaje"])
    return redirect("oportunidades:laboratorio_sesion", sesion_id=sesion.pk)


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
    resultados = ResultadoExtraccionWeb.objects.filter(ejecucion__conector=extractor.conector).order_by("-score_preview", "-fecha_creacion")[:20]
    return render(
        request,
        "oportunidades/detalle_extractor.html",
        {
            "extractor": extractor,
            "validacion": validar_ejecucion_extractor(extractor.conector),
            "condiciones_faltantes": obtener_condiciones_faltantes_extractor(extractor.conector),
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


def selectores_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb, pk=pk)
    form = ConfiguracionExtractorWebForm(request.POST or None, instance=extractor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Selectores y configuracion de preview guardados.")
        return redirect("oportunidades:detalle_extractor", pk=extractor.pk)
    return render(request, "oportunidades/selectores_extractor.html", {"form": form, "extractor": extractor})


@require_POST
def probar_selectores_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
    resultado = probar_url_preview(extractor)
    if resultado["ok"]:
        messages.success(request, extractor.ultimo_preview_mensaje)
    else:
        messages.warning(request, extractor.ultimo_preview_mensaje or "Preview finalizado sin productos detectados.")
    return render(
        request,
        "oportunidades/resultado_preview_selectores.html",
        {"extractor": extractor, "resultado": resultado},
    )


def resultados_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
    ejecucion = extractor.conector.ejecuciones.prefetch_related("resultados_web").first()
    if ejecucion:
        rankear_resultados_ejecucion(ejecucion)
    resultados = ejecucion.resultados_web.order_by("-score_preview", "-fecha_creacion") if ejecucion else ResultadoExtraccionWeb.objects.none()
    validaciones = [(resultado, validar_resultado_procesable(resultado)) for resultado in resultados]
    return render(
        request,
        "oportunidades/resultados_extractor.html",
        {"extractor": extractor, "ejecucion": ejecucion, "validaciones": validaciones},
    )


def resultados_pendientes_extractores(request):
    resultados = (
        ResultadoExtraccionWeb.objects.select_related("ejecucion__conector__fuente_web", "producto_fuente")
        .filter(estado=ResultadoExtraccionWeb.ESTADO_DETECTADO, procesable=True, producto_fuente__isnull=True)
        .order_by("-score_preview", "-fecha_creacion")[:100]
    )
    return render(request, "oportunidades/resultados_pendientes.html", {"resultados": resultados})


@require_POST
def seleccionar_resultado_extractor(request, resultado_id):
    resultado = get_object_or_404(ResultadoExtraccionWeb.objects.select_related("ejecucion__conector"), pk=resultado_id)
    seleccionado = request.POST.get("seleccionado") != "0"
    marcar_resultado_seleccionado(resultado.pk, seleccionado)
    messages.success(request, "Seleccion actualizada.")
    return redirect("oportunidades:resultados_extractor", pk=resultado.ejecucion.conector.configuracion_web.pk)


@require_POST
def seleccionar_mejores_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
    ejecucion = extractor.conector.ejecuciones.prefetch_related("resultados_web").first()
    if not ejecucion:
        messages.warning(request, "No hay ejecucion preview para seleccionar.")
        return redirect("oportunidades:detalle_extractor", pk=extractor.pk)
    rankear_resultados_ejecucion(ejecucion)
    limite = min(int(request.POST.get("limite", 10)), 20)
    seleccionados = 0
    for resultado in ejecucion.resultados_web.filter(
        estado=ResultadoExtraccionWeb.ESTADO_DETECTADO,
        procesable=True,
        producto_fuente__isnull=True,
        duplicado_probable=False,
    ).order_by("-score_preview", "-fecha_creacion")[:limite]:
        if resultado.score_preview >= 50:
            resultado.seleccionado = True
            resultado.save(update_fields=["seleccionado"])
            seleccionados += 1
    messages.success(request, f"Se seleccionaron {seleccionados} resultados mejor rankeados.")
    return redirect("oportunidades:resultados_extractor", pk=extractor.pk)


@require_POST
def limpiar_seleccion_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb, pk=pk)
    ResultadoExtraccionWeb.objects.filter(ejecucion__conector=extractor.conector).update(seleccionado=False)
    messages.success(request, "Seleccion limpiada.")
    return redirect("oportunidades:resultados_extractor", pk=extractor.pk)


@require_POST
def seleccionar_todos_procesables_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb, pk=pk)
    actualizados = 0
    for resultado in ResultadoExtraccionWeb.objects.filter(ejecucion__conector=extractor.conector):
        if validar_resultado_procesable(resultado)["valido"]:
            resultado.seleccionado = True
            resultado.save(update_fields=["seleccionado"])
            actualizados += 1
    messages.success(request, f"{actualizados} resultados procesables seleccionados.")
    return redirect("oportunidades:resultados_extractor", pk=extractor.pk)


def confirmar_procesamiento_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
    cantidad = ResultadoExtraccionWeb.objects.filter(ejecucion__conector=extractor.conector, seleccionado=True).count()
    return render(
        request,
        "oportunidades/confirmar_procesamiento.html",
        {"extractor": extractor, "cantidad": cantidad},
    )


@require_POST
def procesar_seleccionados_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
    ejecucion = extractor.conector.ejecuciones.first()
    if not ejecucion:
        messages.warning(request, "No hay ejecucion con resultados.")
        return redirect("oportunidades:detalle_extractor", pk=extractor.pk)
    resumen = procesar_resultados_seleccionados(ejecucion, limite=20)
    messages.success(
        request,
        f"Procesados={resumen['procesados']}, errores={resumen['errores']}, precios={resumen['precios_creados']}.",
    )
    return redirect("oportunidades:resultados_extractor", pk=extractor.pk)


def diagnostico_js_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb, pk=pk)
    diagnostico = diagnosticar_requiere_headless(extractor)
    comparacion = comparar_html_requests_vs_headless(extractor)
    return render(
        request,
        "oportunidades/diagnostico_js_extractor.html",
        {"extractor": extractor, "diagnostico": diagnostico, "comparacion": comparacion},
    )


def estado_operativo_decohome(request):
    fuente, _ = preparar_decohome()
    conector = fuente.conectores.filter(tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO).first()
    extractor = ConfiguracionExtractorWeb.objects.filter(conector=conector).first() if conector else None
    faltantes = obtener_condiciones_faltantes_extractor(conector) if conector else ["falta conector"]
    resultados = ResultadoExtraccionWeb.objects.filter(ejecucion__conector=conector)[:20] if conector else []
    return render(
        request,
        "oportunidades/estado_operativo_decohome.html",
        {"fuente": fuente, "conector": conector, "extractor": extractor, "faltantes": faltantes, "resultados": resultados},
    )


def estado_operativo_fuente(request, pk):
    fuente = get_object_or_404(FuenteWeb, pk=pk)
    estado = evaluar_estado_operativo_fuente(fuente)
    resultados = (
        ResultadoExtraccionWeb.objects.filter(ejecucion__conector=estado["conector"]).order_by("-score_preview", "-fecha_creacion")[:20]
        if estado["conector"]
        else []
    )
    return render(
        request,
        "oportunidades/estado_operativo_fuente.html",
        {"fuente": fuente, "estado": estado, "resultados": resultados},
    )


def selectores_decohome(request):
    fuente = FuenteWeb.objects.filter(nombre="Deco Home").first()
    if not fuente:
        messages.warning(request, "Primero ejecuta preparar_decohome.")
        return redirect("oportunidades:lista_fuentes")
    conector = fuente.conectores.filter(tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO).first()
    if not conector:
        messages.warning(request, "Deco Home no tiene conector web. Ejecuta configurar_extractor_decohome.")
        return redirect("oportunidades:detalle_fuente", pk=fuente.pk)
    try:
        extractor = conector.configuracion_web
    except ConfiguracionExtractorWeb.DoesNotExist:
        messages.warning(request, "Primero ejecuta configurar_extractor_decohome.")
        return redirect("oportunidades:detalle_conector", pk=conector.pk)
    return redirect("oportunidades:selectores_extractor", pk=extractor.pk)


@require_POST
def preview_extractor(request, pk):
    extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
    resultado = probar_url_preview(extractor)
    if resultado["errores"]:
        messages.error(request, extractor.ultimo_preview_mensaje or "Preview finalizado con errores.")
    else:
        messages.success(request, extractor.ultimo_preview_mensaje or "Preview finalizado.")
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
    return render(
        request,
        "oportunidades/lista_productos_multifuente.html",
        {"productos": productos, "advertencia_persistencia": obtener_advertencia_persistencia()},
    )


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
    return render(
        request,
        "oportunidades/detalle_producto_multifuente.html",
        {"producto": producto, "advertencia_persistencia": obtener_advertencia_persistencia()},
    )


def _ultimo_precio_producto(producto_fuente):
    return producto_fuente.precios_fuente.order_by("-fecha_relevamiento", "-id").first()


def curaduria_productos(request):
    productos = ProductoFuente.objects.select_related("fuente_web", "producto_canonico").prefetch_related("precios_fuente")
    fuente_id = request.GET.get("fuente")
    revision = request.GET.get("revision")
    url = request.GET.get("url")
    imagen = request.GET.get("imagen")
    q = request.GET.get("q")
    if fuente_id:
        productos = productos.filter(fuente_web_id=fuente_id)
    if revision == "pendiente":
        productos = productos.filter(requiere_revision=True)
    elif revision == "revisado":
        productos = productos.filter(revisado=True)
    if url == "tecnica":
        productos = productos.filter(url_tecnica_generada=True)
    elif url == "real":
        productos = productos.filter(url_tecnica_generada=False)
    if imagen == "sin":
        productos = productos.filter(Q(imagen_url__isnull=True) | Q(imagen_url=""))
    elif imagen == "con":
        productos = productos.exclude(Q(imagen_url__isnull=True) | Q(imagen_url=""))
    if q:
        productos = productos.filter(Q(titulo_original__icontains=q) | Q(producto_canonico__nombre_normalizado__icontains=q))
    productos = productos.order_by("-requiere_revision", "-fecha_actualizacion")[:300]
    return render(
        request,
        "oportunidades/curaduria_productos.html",
        {
            "productos": productos,
            "fuentes": FuenteWeb.objects.filter(activa=True).order_by("nombre"),
            "advertencia_persistencia": obtener_advertencia_persistencia(),
        },
    )


def detalle_curaduria_producto(request, pk):
    producto = get_object_or_404(
        ProductoFuente.objects.select_related("fuente_web", "producto_canonico").prefetch_related("precios_fuente"),
        pk=pk,
    )
    duplicados = detectar_producto_fuente_duplicados(producto)
    previews = ResultadoExtraccionWeb.objects.filter(producto_fuente=producto).order_by("-fecha_creacion")[:50]
    operaciones = OperacionCuraduria.objects.filter(producto_fuente=producto)[:50]
    return render(
        request,
        "oportunidades/detalle_curaduria_producto.html",
        {
            "producto": producto,
            "ultimo_precio": _ultimo_precio_producto(producto),
            "duplicados": duplicados,
            "previews": previews,
            "operaciones": operaciones,
            "advertencia_persistencia": obtener_advertencia_persistencia(),
        },
    )


@require_POST
def marcar_revision_producto(request, pk):
    producto = get_object_or_404(ProductoFuente, pk=pk)
    marcar_requiere_revision(producto, request.POST.get("motivo") or "Marcado manualmente para revision.")
    messages.success(request, "Producto marcado para revision.")
    return redirect("oportunidades:detalle_curaduria_producto", pk=pk)


@require_POST
def marcar_revisado_producto(request, pk):
    producto = get_object_or_404(ProductoFuente, pk=pk)
    marcar_revisado(producto)
    messages.success(request, "Producto marcado como revisado.")
    return redirect("oportunidades:detalle_curaduria_producto", pk=pk)


def reasignar_canonico_producto(request, pk):
    producto = get_object_or_404(ProductoFuente.objects.select_related("producto_canonico"), pk=pk)
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "desvincular":
            canonico = None
        elif accion == "crear":
            canonico = crear_producto_canonico_desde_fuente(producto)
        else:
            canonico_id = request.POST.get("producto_canonico")
            canonico = get_object_or_404(ProductoCanonico, pk=canonico_id) if canonico_id else None
        reasignar_producto_canonico(producto, canonico)
        messages.success(request, "Producto canonico actualizado.")
        return redirect("oportunidades:detalle_curaduria_producto", pk=producto.pk)
    return render(
        request,
        "oportunidades/reasignar_canonico_producto.html",
        {"producto": producto, "canonicos": ProductoCanonico.objects.order_by("nombre_normalizado")[:500]},
    )


def curaduria_previews(request):
    resultados = ResultadoExtraccionWeb.objects.select_related("ejecucion__conector__fuente_web", "producto_fuente")
    estado = request.GET.get("estado")
    fuente_id = request.GET.get("fuente")
    if estado == "procesados":
        resultados = resultados.filter(producto_fuente__isnull=False)
    elif estado == "pendientes":
        resultados = resultados.filter(producto_fuente__isnull=True)
    elif estado == "sin_url":
        resultados = resultados.filter(Q(url_producto__isnull=True) | Q(url_producto=""))
    elif estado == "sin_imagen":
        resultados = resultados.filter(Q(imagen_url__isnull=True) | Q(imagen_url=""))
    if fuente_id:
        resultados = resultados.filter(ejecucion__conector__fuente_web_id=fuente_id)
    return render(
        request,
        "oportunidades/curaduria_previews.html",
        {
            "resultados": resultados.order_by("-fecha_creacion")[:300],
            "fuentes": FuenteWeb.objects.filter(activa=True).order_by("nombre"),
            "advertencia_persistencia": obtener_advertencia_persistencia(),
        },
    )


@require_POST
def reprocesar_preview(request, pk):
    resultado = get_object_or_404(ResultadoExtraccionWeb, pk=pk)
    resultado.estado = ResultadoExtraccionWeb.ESTADO_DETECTADO
    resultado.producto_fuente = None
    resultado.procesable = True
    resultado.seleccionado = True
    resultado.save(update_fields=["estado", "producto_fuente", "procesable", "seleccionado"])
    resumen = procesar_resultados_seleccionados(resultado.ejecucion, limite=1)
    messages.success(request, f"Reprocesado: {resumen['procesados']} procesado(s), {resumen['errores']} error(es).")
    return redirect("oportunidades:curaduria_previews")


def dataset_exportar(request):
    tipo = request.GET.get("tipo")
    if tipo == "productos":
        response = HttpResponse(exportar_dataset_productos_csv().getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="productos_dataset.csv"'
        return response
    if tipo == "historial":
        response = HttpResponse(exportar_historial_precios_csv().getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="historial_precios.csv"'
        return response
    if tipo == "previews":
        response = HttpResponse(exportar_resultados_preview_csv().getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="resultados_preview.csv"'
        return response
    if tipo == "zip":
        response = HttpResponse(exportar_dataset_completo_zip().getvalue(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="radar_dataset.zip"'
        return response
    return render(request, "oportunidades/dataset_exportar.html", {"advertencia_persistencia": obtener_advertencia_persistencia()})


def dataset_backup(request):
    if request.GET.get("exportar") == "snapshot":
        response = HttpResponse(exportar_snapshot_json(), content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="snapshot_radar.json"'
        return response
    return render(
        request,
        "oportunidades/dataset_backup.html",
        {
            "advertencia_persistencia": obtener_advertencia_persistencia(),
            "resumen": snapshot_resumen_json(),
        },
    )


def ranking_oportunidades(request):
    if request.GET.get("recalcular") == "1":
        recalcular_ranking_comercial()
        messages.success(request, "Ranking comercial recalculado.")
        return redirect("oportunidades:ranking_oportunidades")
    productos = ProductoFuente.objects.select_related("fuente_web", "producto_canonico").prefetch_related("precios_fuente").order_by("-score_comercial", "-fecha_actualizacion")[:300]
    for producto in productos:
        if not producto.score_comercial:
            calcular_score_comercial_producto_fuente(producto)
    return render(
        request,
        "oportunidades/ranking_oportunidades.html",
        {"productos": productos, "advertencia_persistencia": obtener_advertencia_persistencia()},
    )


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


class RevisionManualFuenteListAPIView(generics.ListAPIView):
    queryset = RevisionManualFuente.objects.select_related("fuente_web").all()
    serializer_class = RevisionManualFuenteSerializer


class FuenteRevisionManualCreateAPIView(APIView):
    def post(self, request, pk):
        fuente = get_object_or_404(FuenteWeb, pk=pk)
        serializer = RevisionManualFuenteSerializer(data={**request.data, "fuente_web": fuente.pk})
        serializer.is_valid(raise_exception=True)
        revision = serializer.save(fuente_web=fuente)
        if revision.aplicar_a_politica:
            aplicar_revision_a_politica(revision)
        return Response(RevisionManualFuenteSerializer(revision).data, status=status.HTTP_201_CREATED)


class ExtractorSelectoresAPIView(generics.RetrieveUpdateAPIView):
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


class ExtractorProbarSelectoresAPIView(APIView):
    def post(self, request, pk):
        extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
        resultado = probar_url_preview(extractor)
        return Response(
            {
                "ok": resultado["ok"],
                "productos_detectados": resultado["productos_detectados"],
                "muestras": resultado["muestras"],
                "errores": resultado["errores"],
                "diagnostico": resultado["diagnostico"],
                "ejecucion": EjecucionConectorSerializer(resultado["ejecucion"]).data,
            },
            status=status.HTTP_200_OK,
        )


class ExtractorResultadosAPIView(generics.ListAPIView):
    serializer_class = ResultadoExtraccionWebSerializer

    def get_queryset(self):
        return ResultadoExtraccionWeb.objects.filter(ejecucion__conector__configuracion_web_id=self.kwargs["pk"])


class ResultadoSeleccionarAPIView(APIView):
    def post(self, request, resultado_id):
        seleccionado = bool(request.data.get("seleccionado", True))
        resultado = marcar_resultado_seleccionado(resultado_id, seleccionado)
        return Response(ResultadoExtraccionWebSerializer(resultado).data, status=status.HTTP_200_OK)


class ExtractorProcesarSeleccionadosAPIView(APIView):
    def post(self, request, pk):
        extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
        ejecucion = extractor.conector.ejecuciones.first()
        if not ejecucion:
            return Response({"detail": "No hay ejecucion con resultados."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(procesar_resultados_seleccionados(ejecucion), status=status.HTTP_200_OK)


class ExtractorDiagnosticoJSAPIView(APIView):
    def get(self, request, pk):
        extractor = get_object_or_404(ConfiguracionExtractorWeb, pk=pk)
        return Response(diagnosticar_requiere_headless(extractor), status=status.HTTP_200_OK)


class FuenteEstadoOperativoListAPIView(APIView):
    def get(self, request):
        data = []
        for fuente in FuenteWeb.objects.all():
            estado = evaluar_estado_operativo_fuente(fuente)
            data.append(
                {
                    "fuente": FuenteWebSerializer(fuente).data,
                    "estado": estado["estado"],
                    "puede_preview": estado["puede_preview"],
                    "puede_procesar": estado["puede_procesar"],
                    "requiere_js": estado["requiere_js"],
                    "faltantes": estado["faltantes"],
                    "recomendacion": estado["recomendacion"],
                }
            )
        return Response(data, status=status.HTTP_200_OK)


class FuenteEstadoOperativoAPIView(APIView):
    def get(self, request, pk):
        fuente = get_object_or_404(FuenteWeb, pk=pk)
        estado = evaluar_estado_operativo_fuente(fuente)
        return Response(
            {
                "fuente": FuenteWebSerializer(fuente).data,
                "estado": estado["estado"],
                "puede_preview": estado["puede_preview"],
                "puede_procesar": estado["puede_procesar"],
                "requiere_js": estado["requiere_js"],
                "faltantes": estado["faltantes"],
                "recomendacion": estado["recomendacion"],
            },
            status=status.HTTP_200_OK,
        )


class FuentePreviewAPIView(APIView):
    def post(self, request, pk):
        fuente = get_object_or_404(FuenteWeb, pk=pk)
        estado_fuente = evaluar_estado_operativo_fuente(fuente)
        if not estado_fuente["puede_preview"]:
            return Response({"detail": "Preview bloqueado.", "faltantes": estado_fuente["faltantes"]}, status=status.HTTP_400_BAD_REQUEST)
        resultado = probar_url_preview(estado_fuente["extractor"])
        return Response(
            {
                "ok": resultado["ok"],
                "ejecucion_id": resultado["ejecucion"].pk if resultado.get("ejecucion") else None,
                "productos_detectados": resultado["productos_detectados"],
                "muestras": resultado["muestras"],
                "errores": resultado["errores"],
                "diagnostico": resultado["diagnostico"],
            },
            status=status.HTTP_200_OK,
        )


class ExtractorSeleccionarMejoresAPIView(APIView):
    def post(self, request, pk):
        extractor = get_object_or_404(ConfiguracionExtractorWeb.objects.select_related("conector"), pk=pk)
        ejecucion = extractor.conector.ejecuciones.prefetch_related("resultados_web").first()
        if not ejecucion:
            return Response({"detail": "No hay ejecucion preview."}, status=status.HTTP_400_BAD_REQUEST)
        rankear_resultados_ejecucion(ejecucion)
        limite = min(int(request.data.get("limite", 10)), 20)
        ids = []
        for resultado in ejecucion.resultados_web.filter(
            estado=ResultadoExtraccionWeb.ESTADO_DETECTADO,
            procesable=True,
            producto_fuente__isnull=True,
            duplicado_probable=False,
        ).order_by("-score_preview", "-fecha_creacion")[:limite]:
            if resultado.score_preview >= 50:
                resultado.seleccionado = True
                resultado.save(update_fields=["seleccionado"])
                ids.append(resultado.pk)
        return Response({"seleccionados": ids}, status=status.HTTP_200_OK)


class ExtractorResultadosPendientesAPIView(generics.ListAPIView):
    serializer_class = ResultadoExtraccionWebSerializer

    def get_queryset(self):
        return (
            ResultadoExtraccionWeb.objects.filter(
                estado=ResultadoExtraccionWeb.ESTADO_DETECTADO,
                procesable=True,
                producto_fuente__isnull=True,
            )
            .select_related("ejecucion__conector__fuente_web")
            .order_by("-score_preview", "-fecha_creacion")
        )


class ExtractorDiagnosticoHeadlessAPIView(APIView):
    def post(self, request, pk):
        extractor = get_object_or_404(ConfiguracionExtractorWeb, pk=pk)
        return Response(comparar_html_requests_vs_headless(extractor), status=status.HTTP_200_OK)


class LaboratorioAnalizarAPIView(APIView):
    def post(self, request):
        resultado = analizar_url_laboratorio(
            request.data.get("url"),
            limite=request.data.get("limite", 10),
            modo=request.data.get("modo", "auto"),
        )
        fuente = FuenteWeb.objects.filter(pk=request.data.get("fuente_id")).first()
        sesion = crear_sesion_laboratorio(resultado, fuente_web=fuente)
        return Response(
            {"sesion": SesionLaboratorioMapeoSerializer(sesion).data, "resultado": resultado},
            status=status.HTTP_201_CREATED if resultado["ok"] else status.HTTP_400_BAD_REQUEST,
        )


class LaboratorioSesionesAPIView(generics.ListAPIView):
    queryset = SesionLaboratorioMapeo.objects.prefetch_related("resultados").select_related("fuente_web").all()
    serializer_class = SesionLaboratorioMapeoSerializer


class LaboratorioSesionDetailAPIView(generics.RetrieveAPIView):
    queryset = SesionLaboratorioMapeo.objects.prefetch_related("resultados").select_related("fuente_web").all()
    serializer_class = SesionLaboratorioMapeoSerializer


class LaboratorioProcesarSeleccionadosAPIView(APIView):
    def post(self, request, pk):
        sesion = get_object_or_404(SesionLaboratorioMapeo, pk=pk)
        resumen = procesar_resultados_laboratorio(sesion, limite=10)
        return Response(resumen, status=status.HTTP_200_OK if resumen["ok"] else status.HTTP_400_BAD_REQUEST)


class FuenteLaboratorioAnalizarAPIView(APIView):
    def post(self, request, pk):
        fuente = get_object_or_404(FuenteWeb, pk=pk)
        resultado = analizar_url_laboratorio(
            request.data.get("url") or fuente.url_base,
            limite=request.data.get("limite", 10),
            modo=request.data.get("modo", "auto"),
        )
        sesion = crear_sesion_laboratorio(resultado, fuente_web=fuente)
        return Response(
            {"sesion": SesionLaboratorioMapeoSerializer(sesion).data, "resultado": resultado},
            status=status.HTTP_201_CREATED if resultado["ok"] else status.HTTP_400_BAD_REQUEST,
        )


class FuenteWizardNuevaAPIView(APIView):
    def post(self, request):
        form = FuenteWizardForm(request.data)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        fuente, _ = crear_fuente_wizard(form.cleaned_data)
        return Response(FuenteWebSerializer(fuente).data, status=status.HTTP_201_CREATED)


class FuenteGenericaPrepararAPIView(APIView):
    def post(self, request):
        nombre = request.data.get("nombre")
        url_base = request.data.get("url_base")
        if not nombre or not url_base:
            return Response({"detail": "nombre y url_base son requeridos."}, status=status.HTTP_400_BAD_REQUEST)
        fuente, conector, _, _ = preparar_fuente_generica(nombre, url_base, request.data.get("rubro", ""))
        return Response({"fuente": FuenteWebSerializer(fuente).data, "conector": ConectorFuenteSerializer(conector).data})


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
