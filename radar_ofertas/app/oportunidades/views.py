from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import OportunidadFiltroForm
from .models import Oportunidad
from .serializers import (
    ContenidoSugeridoSerializer,
    OportunidadDetalleSerializer,
    OportunidadEstadoSerializer,
    OportunidadSerializer,
)
from .services.clasificacion_service import clasificar_oportunidad
from .services.contenido_service import generar_contenido_basico


def lista_oportunidades(request):
    form = OportunidadFiltroForm(request.GET or None)
    oportunidades = (
        Oportunidad.objects.select_related("producto", "producto__categoria", "producto__fuente")
        .all()
    )

    if form.is_valid():
        tipo = form.cleaned_data.get("tipo")
        estado = form.cleaned_data.get("estado")
        categoria = form.cleaned_data.get("categoria")

        if tipo:
            oportunidades = oportunidades.filter(tipo=tipo)
        if estado:
            oportunidades = oportunidades.filter(estado=estado)
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
    return render(request, "oportunidades/detalle_oportunidad.html", {"oportunidad": oportunidad})


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
