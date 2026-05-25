from django.contrib import messages
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import MercadoLibreBusquedaForm, OportunidadFiltroForm
from .models import CategoriaInteres, ConsultaMercadoLibre, MercadoLibreToken, Oportunidad
from .serializers import (
    ContenidoSugeridoSerializer,
    ConsultaMercadoLibreSerializer,
    MeliSincronizarSerializer,
    OportunidadDetalleSerializer,
    OportunidadEstadoSerializer,
    OportunidadSerializer,
)
from .services.clasificacion_service import clasificar_oportunidad
from .services.contenido_service import generar_contenido_basico
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
