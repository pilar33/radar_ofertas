from django.shortcuts import redirect
from django.urls import path

from . import views


app_name = "oportunidades"

urlpatterns = [
    path("", lambda request: redirect("oportunidades:lista"), name="inicio"),
    path("oportunidades/", views.lista_oportunidades, name="lista"),
    path("oportunidades/<int:pk>/", views.detalle_oportunidad, name="detalle"),
    path("oportunidades/<int:pk>/estado/<str:nuevo_estado>/", views.cambiar_estado_oportunidad, name="cambiar_estado"),
    path("api/oportunidades/", views.OportunidadListAPIView.as_view(), name="api_lista"),
    path("api/oportunidades/<int:pk>/", views.OportunidadDetailAPIView.as_view(), name="api_detalle"),
    path("api/oportunidades/<int:pk>/estado/", views.OportunidadEstadoAPIView.as_view(), name="api_estado"),
]
