from django.shortcuts import redirect
from django.urls import path

from . import views


app_name = "oportunidades"

urlpatterns = [
    path("", lambda request: redirect("oportunidades:lista"), name="inicio"),
    path("oportunidades/", views.lista_oportunidades, name="lista"),
    path("oportunidades/<int:pk>/", views.detalle_oportunidad, name="detalle"),
    path("oportunidades/<int:pk>/estado/<str:nuevo_estado>/", views.cambiar_estado_oportunidad, name="cambiar_estado"),
    path("oportunidades/<int:pk>/recalcular/", views.recalcular_oportunidad, name="recalcular"),
    path("oportunidades/<int:pk>/generar-contenido/", views.generar_contenido_oportunidad, name="generar_contenido"),
    path("mercadolibre/buscar/", views.buscar_mercado_libre, name="buscar_meli"),
    path("mercadolibre/oauth/iniciar/", views.oauth_iniciar, name="oauth_iniciar"),
    path("mercadolibre/oauth/callback/", views.oauth_callback, name="oauth_callback"),
    path("mercadolibre/oauth/diagnostico/", views.oauth_diagnostico, name="oauth_diagnostico"),
    path("api/oportunidades/", views.OportunidadListAPIView.as_view(), name="api_lista"),
    path("api/oportunidades/<int:pk>/", views.OportunidadDetailAPIView.as_view(), name="api_detalle"),
    path("api/oportunidades/<int:pk>/estado/", views.OportunidadEstadoAPIView.as_view(), name="api_estado"),
    path("api/oportunidades/<int:pk>/recalcular/", views.OportunidadRecalcularAPIView.as_view(), name="api_recalcular"),
    path(
        "api/oportunidades/<int:pk>/generar-contenido/",
        views.OportunidadGenerarContenidoAPIView.as_view(),
        name="api_generar_contenido",
    ),
    path("api/meli/buscar/", views.MeliBuscarAPIView.as_view(), name="api_meli_buscar"),
    path("api/meli/sincronizar/", views.MeliSincronizarAPIView.as_view(), name="api_meli_sincronizar"),
    path("api/meli/consultas/", views.MeliConsultasAPIView.as_view(), name="api_meli_consultas"),
]
