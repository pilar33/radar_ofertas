from django.contrib import admin

from .models import (
    AuditoriaFuenteWeb,
    CategoriaInteres,
    CategoriaFuente,
    ComparacionPrecio,
    ConectorFuente,
    ConfiguracionExtractorWeb,
    ContenidoSugerido,
    ConsultaMercadoLibre,
    DecisionTecnica,
    DetalleImportacionProducto,
    DetalleEjecucionConector,
    EjecucionConector,
    EvaluacionOportunidadMultifuente,
    FuenteProducto,
    FuenteWeb,
    ImportacionProductos,
    MercadoLibreToken,
    Oportunidad,
    OperacionCuraduria,
    PoliticaExtraccionFuente,
    PrecioProducto,
    PrecioFuente,
    Producto,
    ProductoCanonico,
    ProductoFuente,
    Publicacion,
    RecursoFuenteDetectado,
    RevisionManualFuente,
    ResultadoExtraccionWeb,
    ResultadoLaboratorioMapeo,
    SesionLaboratorioMapeo,
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
    list_display = (
        "titulo",
        "codigo_externo",
        "fuente",
        "categoria",
        "vendedor",
        "cantidad_vendida",
        "disponible",
        "fecha_alta",
    )
    list_filter = ("categoria", "fuente", "disponible", "afiliado_activo", "es_chico_liviano", "es_fragil")
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


@admin.register(ConsultaMercadoLibre)
class ConsultaMercadoLibreAdmin(admin.ModelAdmin):
    list_display = (
        "query",
        "categoria",
        "site_id",
        "status_code",
        "cantidad_resultados",
        "exitosa",
        "requiere_token",
        "forbidden",
        "uso_token",
        "fecha_consulta",
    )
    list_filter = ("exitosa", "forbidden", "requiere_token", "uso_token", "site_id", "categoria", "fecha_consulta")
    search_fields = ("query", "mensaje_error")


@admin.register(MercadoLibreToken)
class MercadoLibreTokenAdmin(admin.ModelAdmin):
    list_display = ("nickname", "user_id_meli", "activo", "expires_at", "fecha_actualizacion")
    list_filter = ("activo", "expires_at", "fecha_actualizacion")
    search_fields = ("nickname", "user_id_meli")
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")


@admin.register(FuenteWeb)
class FuenteWebAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo_fuente", "rubro_principal", "activa", "prioridad", "pais")
    list_filter = ("tipo_fuente", "activa", "pais")
    search_fields = ("nombre", "rubro_principal", "descripcion")


@admin.register(PoliticaExtraccionFuente)
class PoliticaExtraccionFuenteAdmin(admin.ModelAdmin):
    list_display = (
        "fuente",
        "semaforo",
        "metodo_preferido",
        "permite_scraping",
        "tiene_api",
        "tiene_afiliados",
        "riesgo_tecnico",
        "riesgo_legal",
    )
    list_filter = ("semaforo", "metodo_preferido", "permite_scraping", "tiene_api", "riesgo_tecnico", "riesgo_legal")
    search_fields = ("fuente__nombre", "observaciones")


@admin.register(CategoriaFuente)
class CategoriaFuenteAdmin(admin.ModelAdmin):
    list_display = ("fuente", "nombre", "categoria_normalizada", "activa", "prioridad", "fecha_creacion")
    list_filter = ("fuente", "activa", "categoria_normalizada")
    search_fields = ("nombre", "fuente__nombre")


@admin.register(ProductoCanonico)
class ProductoCanonicoAdmin(admin.ModelAdmin):
    list_display = ("nombre_normalizado", "categoria", "marca", "es_chico_liviano", "es_fragil", "estacionalidad")
    list_filter = ("categoria", "es_chico_liviano", "es_fragil", "estacionalidad")
    search_fields = ("nombre_normalizado", "marca", "modelo", "atributos_clave")


@admin.register(ProductoFuente)
class ProductoFuenteAdmin(admin.ModelAdmin):
    list_display = (
        "titulo_original",
        "fuente_web",
        "categoria_fuente",
        "disponible",
        "condicion",
        "requiere_revision",
        "revisado",
        "url_tecnica_generada",
        "score_comercial",
        "fecha_actualizacion",
    )
    list_filter = ("fuente_web", "categoria_fuente", "disponible", "condicion", "requiere_revision", "revisado", "url_tecnica_generada")
    search_fields = ("titulo_original", "codigo_externo", "vendedor", "marca_detectada")


@admin.register(PrecioFuente)
class PrecioFuenteAdmin(admin.ModelAdmin):
    list_display = (
        "producto_fuente",
        "precio",
        "precio_lista",
        "precio_transferencia",
        "precio_tarjeta",
        "precio_oportunidad",
        "tipo_precio_oportunidad",
        "moneda",
        "origen_dato",
        "fecha_relevamiento",
    )
    list_filter = ("moneda", "origen_dato", "tipo_precio_oportunidad", "fecha_relevamiento")
    search_fields = ("producto_fuente__titulo_original",)


@admin.register(OperacionCuraduria)
class OperacionCuraduriaAdmin(admin.ModelAdmin):
    list_display = ("tipo_operacion", "producto_fuente", "producto_canonico", "fecha", "usuario_texto")
    list_filter = ("tipo_operacion", "fecha")
    search_fields = ("descripcion", "producto_fuente__titulo_original", "producto_canonico__nombre_normalizado")


@admin.register(ComparacionPrecio)
class ComparacionPrecioAdmin(admin.ModelAdmin):
    list_display = ("producto_canonico", "precio_minimo", "precio_promedio", "precio_maximo", "cantidad_fuentes", "fecha_calculo")
    list_filter = ("fecha_calculo", "fuente_mas_barata")
    search_fields = ("producto_canonico__nombre_normalizado",)


@admin.register(EvaluacionOportunidadMultifuente)
class EvaluacionOportunidadMultifuenteAdmin(admin.ModelAdmin):
    list_display = ("producto_canonico", "tipo", "riesgo", "indice_oportunidad", "porcentaje_margen", "fecha_creacion")
    list_filter = ("tipo", "riesgo", "fecha_creacion")
    search_fields = ("producto_canonico__nombre_normalizado", "motivo")


@admin.register(DecisionTecnica)
class DecisionTecnicaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "fecha")
    list_filter = ("categoria", "fecha")
    search_fields = ("titulo", "descripcion", "decision", "motivo", "impacto")


@admin.register(AuditoriaFuenteWeb)
class AuditoriaFuenteWebAdmin(admin.ModelAdmin):
    list_display = (
        "fuente_web",
        "semaforo_sugerido",
        "metodo_recomendado",
        "status_home",
        "status_robots",
        "status_sitemap",
        "permite_extraccion_segun_revision",
        "fecha_auditoria",
    )
    list_filter = ("semaforo_sugerido", "metodo_recomendado", "permite_extraccion_segun_revision", "fuente_web")
    search_fields = ("fuente_web__nombre", "resumen_tecnico", "riesgos_detectados", "recomendacion")


@admin.register(RecursoFuenteDetectado)
class RecursoFuenteDetectadoAdmin(admin.ModelAdmin):
    list_display = ("auditoria", "tipo_recurso", "url", "status_code", "content_type", "permitido", "fecha_detectado")
    list_filter = ("tipo_recurso", "permitido", "status_code")
    search_fields = ("url", "observaciones", "auditoria__fuente_web__nombre")


@admin.register(RevisionManualFuente)
class RevisionManualFuenteAdmin(admin.ModelAdmin):
    list_display = ("fuente_web", "tipo_revision", "resultado", "aplicar_a_politica", "fecha_revision")
    list_filter = ("tipo_revision", "resultado", "aplicar_a_politica")
    search_fields = ("fuente_web__nombre", "resumen", "decision")


@admin.register(ImportacionProductos)
class ImportacionProductosAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fuente_web",
        "conector",
        "tipo_archivo",
        "estado",
        "total_filas",
        "productos_creados",
        "productos_actualizados",
        "precios_creados",
        "errores",
        "fecha_creacion",
    )
    list_filter = ("estado", "tipo_archivo", "fuente_web", "conector")
    search_fields = ("fuente_web__nombre", "conector__nombre", "observaciones")
    readonly_fields = ("fecha_creacion", "fecha_procesamiento")


@admin.register(DetalleImportacionProducto)
class DetalleImportacionProductoAdmin(admin.ModelAdmin):
    list_display = ("importacion", "numero_fila", "estado", "producto_fuente", "precio_fuente")
    list_filter = ("estado",)
    search_fields = ("mensaje", "datos_originales")


@admin.register(ConectorFuente)
class ConectorFuenteAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "fuente_web",
        "tipo_conector",
        "estado",
        "formato_recurso",
        "requiere_descarga",
        "fuente_autorizo_uso",
        "requiere_revision_manual",
        "respeta_politica_fuente",
        "ultima_ejecucion",
    )
    list_filter = ("tipo_conector", "estado", "fuente_web")
    search_fields = ("nombre", "fuente_web__nombre", "descripcion")


@admin.register(EjecucionConector)
class EjecucionConectorAdmin(admin.ModelAdmin):
    list_display = (
        "conector",
        "estado",
        "inicio",
        "fin",
        "productos_detectados",
        "productos_creados",
        "productos_actualizados",
        "precios_creados",
        "errores",
    )
    list_filter = ("estado", "conector__tipo_conector", "conector__fuente_web")
    search_fields = ("conector__nombre", "mensaje", "log_resumido")


@admin.register(DetalleEjecucionConector)
class DetalleEjecucionConectorAdmin(admin.ModelAdmin):
    list_display = ("ejecucion", "estado", "producto_fuente", "fecha_creacion")
    list_filter = ("estado",)
    search_fields = ("mensaje", "datos_originales")


@admin.register(ConfiguracionExtractorWeb)
class ConfiguracionExtractorWebAdmin(admin.ModelAdmin):
    list_display = (
        "conector",
        "dominio_permitido",
        "pagina_prueba_url",
        "modo_extraccion",
        "habilitado",
        "solo_preview",
        "requiere_js_detectado",
        "ultimo_preview_ok",
        "ultima_revision_selectores",
        "max_paginas",
        "max_productos",
        "delay_segundos",
    )
    list_filter = ("modo_extraccion", "habilitado", "solo_preview")
    search_fields = ("conector__nombre", "conector__fuente_web__nombre", "dominio_permitido")


@admin.register(ResultadoExtraccionWeb)
class ResultadoExtraccionWebAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "precio_decimal",
        "precio_oportunidad_decimal",
        "tipo_precio_oportunidad",
        "score_preview",
        "duplicado_probable",
        "estado",
        "seleccionado",
        "procesable",
        "producto_fuente",
        "fecha_creacion",
    )
    list_filter = (
        "estado",
        "tipo_precio_oportunidad",
        "seleccionado",
        "procesable",
        "duplicado_probable",
        "ejecucion__conector__fuente_web",
    )
    search_fields = ("titulo", "url_producto", "mensaje", "motivo_score")


@admin.register(SesionLaboratorioMapeo)
class SesionLaboratorioMapeoAdmin(admin.ModelAdmin):
    list_display = ("url", "fuente_web", "estado", "status_code", "requiere_js_probable", "tiene_json_ld", "fecha_creacion")
    list_filter = ("estado", "requiere_js_probable", "tiene_json_ld")
    search_fields = ("url", "fuente_web__nombre")


@admin.register(ResultadoLaboratorioMapeo)
class ResultadoLaboratorioMapeoAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "precio_decimal",
        "precio_oportunidad_decimal",
        "tipo_precio_oportunidad",
        "score",
        "seleccionado",
        "procesado",
    )
    list_filter = ("tipo_precio_oportunidad", "seleccionado", "procesado")
    search_fields = ("titulo", "url_producto")
