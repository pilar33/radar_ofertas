from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    return JsonResponse({"status": "ok", "app": "radar_ofertas"})


urlpatterns = [
    path("health/", health_check, name="health"),
    path("admin/", admin.site.urls),
    path("", include("oportunidades.urls")),
]
