from django.contrib import admin

from .models import (
    CategoriaInteres,
    ContenidoSugerido,
    FuenteProducto,
    Oportunidad,
    PrecioProducto,
    Producto,
    Publicacion,
)


@admin.register(FuenteProducto)
class FuenteProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "activa", "fecha_creacion")
    list_filter = ("tipo", "activa")
    search_fields = ("nombre", "url_base")


@admin.register(CategoriaInteres)
class CategoriaInteresAdmin(admin.ModelAdmin):
    list_display = ("nombre", "palabra_clave", "prioridad", "activa", "fecha_creacion")
    list_filter = ("activa", "prioridad")
    search_fields = ("nombre", "palabra_clave")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "fuente", "vendedor", "es_chico_liviano", "es_fragil", "fecha_alta")
    list_filter = ("categoria", "fuente", "es_chico_liviano", "es_fragil")
    search_fields = ("titulo", "vendedor", "marca", "codigo_externo")


@admin.register(PrecioProducto)
class PrecioProductoAdmin(admin.ModelAdmin):
    list_display = ("producto", "precio", "costo_envio", "moneda", "fecha_relevamiento")
    list_filter = ("moneda", "fecha_relevamiento")
    search_fields = ("producto__titulo",)


@admin.register(Oportunidad)
class OportunidadAdmin(admin.ModelAdmin):
    list_display = (
        "producto",
        "tipo",
        "riesgo",
        "puntaje",
        "porcentaje_margen",
        "estado",
        "fecha_creacion",
    )
    list_filter = ("tipo", "riesgo", "estado", "producto__categoria")
    search_fields = ("producto__titulo", "motivo")


@admin.register(ContenidoSugerido)
class ContenidoSugeridoAdmin(admin.ModelAdmin):
    list_display = ("gancho", "oportunidad", "generado_con_ia", "fecha_creacion")
    list_filter = ("generado_con_ia", "fecha_creacion")
    search_fields = ("gancho", "descripcion", "oportunidad__producto__titulo")


@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    list_display = ("oportunidad", "red_social", "fecha_publicacion", "vistas", "clics", "ventas_reportadas")
    list_filter = ("red_social", "fecha_publicacion")
    search_fields = ("oportunidad__producto__titulo", "url_publicacion", "observaciones")
