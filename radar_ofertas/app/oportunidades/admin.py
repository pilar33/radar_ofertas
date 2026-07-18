from django.contrib import admin

from .models import (
    AuditoriaFuenteWeb,
    CandidatoCompra,
    CompraProducto,
    CategoriaInteres,
    CategoriaFuente,
    ComparacionPrecio,
    ConectorFuente,
    ConfiguracionExtractorWeb,
    ContenidoSugerido,
    ConsultaMercadoLibre,
    DecisionTecnica,
    DuplicadoIgnorado,
    DetalleImportacionProducto,
    DetalleLoteCaptura,
    DetalleEjecucionConector,
    EjecucionConector,
    EvaluacionOportunidadMultifuente,
    FuenteProducto,
    FuenteWeb,
    ImportacionProductos,
    ImportacionRadarTexto,
    ItemRanking,
    LoteRanking,
    LoteCaptura,
    MercadoLibreToken,
    Oportunidad,
    OportunidadRadar,
    OperacionCuraduria,
    PoliticaExtraccionFuente,
    PrecioProducto,
    PrecioFuente,
    Producto,
    ProductoCanonico,
    ProductoFuente,
    Publicacion,
    PublicacionReventa,
    RecursoFuenteDetectado,
    RevisionManualFuente,
    ResultadoExtraccionWeb,
    ResultadoLaboratorioMapeo,
    ResultadoComercialProducto,
    SesionLaboratorioMapeo,
    SenalDemandaProducto,
    SugerenciaMatchingProducto,
    VentaProducto,
)


@admin.register(LoteCaptura)
class LoteCapturaAdmin(admin.ModelAdmin):
    list_display = (
        "id", "nombre", "fuente_web", "origen", "tipo_carga", "estado",
        "productos_detectados", "productos_procesados", "precios_creados", "errores",
        "apto_dataset", "excluir_ml", "fecha_inicio",
    )
    list_filter = ("origen", "tipo_carga", "estado", "apto_dataset", "excluir_ml", "fuente_web")
    search_fields = ("nombre", "url_origen", "observaciones")


@admin.register(DetalleLoteCaptura)
class DetalleLoteCapturaAdmin(admin.ModelAdmin):
    list_display = ("lote", "estado", "producto_fuente", "precio_fuente", "fecha")
    list_filter = ("estado",)
    search_fields = ("mensaje", "datos_originales")


@admin.register(LoteRanking)
class LoteRankingAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo_ranking", "alcance", "categoria", "fecha_referencia", "estado", "cantidad_filas", "origen")
    list_filter = ("tipo_ranking", "estado", "categoria", "fecha_referencia")
    search_fields = ("nombre", "alcance", "origen", "metodologia", "hash_importacion")
    readonly_fields = ("fecha_importacion", "fecha_actualizacion", "hash_importacion", "posible_duplicado")


@admin.register(ItemRanking)
class ItemRankingAdmin(admin.ModelAdmin):
    list_display = (
        "lote",
        "posicion",
        "nombre_original",
        "categoria",
        "tienda",
        "tipo_senal",
        "estado_verificacion",
        "posicion_anterior",
        "tendencia",
        "precio_por_unidad",
        "precio_por_litro",
        "precio_por_kg",
        "precio_por_metro",
    )
    list_filter = ("lote__tipo_ranking", "categoria", "tienda", "tipo_senal", "estado_verificacion", "tendencia", "tipo_presentacion")
    search_fields = ("nombre_original", "tienda", "texto_senal", "url_evidencia", "marca", "subcategoria")
    autocomplete_fields = ("producto_fuente", "producto_canonico", "categoria", "fuente_web")
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")


@admin.register(FuenteProducto)
class FuenteProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "activa", "fecha_creacion")
    list_filter = ("tipo", "activa")
    search_fields = ("nombre", "url_base")


@admin.register(CategoriaInteres)
class CategoriaInteresAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "categoria_padre", "palabra_clave", "prioridad", "activa", "fecha_creacion")
    list_filter = ("activa", "prioridad", "categoria_padre")
    search_fields = ("nombre", "slug", "palabra_clave", "palabras_clave", "marcas_clave")
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "codigo_externo",
        "fuente",
        "categoria_original",
        "categoria",
        "vendedor",
        "cantidad_vendida",
        "disponible",
        "fecha_alta",
    )
    list_filter = ("categoria", "fuente", "disponible", "afiliado_activo", "es_chico_liviano", "es_fragil")
    search_fields = ("titulo", "vendedor", "marca", "codigo_externo", "categoria_original", "subcategoria_original", "etiquetas")


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
        "categoria_original",
        "categoria_fuente",
        "categoria_normalizada",
        "precio_actual",
        "disponible",
        "condicion",
        "requiere_revision",
        "revisado",
        "url_tecnica_generada",
        "score_comercial",
        "score_demanda_actual",
        "nivel_demanda_actual",
        "nivel_oportunidad",
        "fecha_actualizacion",
    )
    list_filter = (
        "fuente_web",
        "categoria_fuente",
        "producto_canonico__categoria",
        "disponible",
        "condicion",
        "requiere_revision",
        "revisado",
        "url_tecnica_generada",
        "nivel_oportunidad",
        "nivel_demanda_actual",
        "descartado_curaduria",
    )
    search_fields = ("titulo_original", "codigo_externo", "vendedor", "marca_detectada", "categoria_original", "subcategoria_original", "etiquetas")
    autocomplete_fields = ("producto_canonico", "categoria_fuente")

    def categoria_normalizada(self, obj):
        if obj.producto_canonico_id:
            return obj.producto_canonico.categoria
        if obj.categoria_fuente_id:
            return obj.categoria_fuente.categoria_normalizada
        return None

    def precio_actual(self, obj):
        precio = obj.precios_fuente.order_by("-fecha_relevamiento", "-id").first()
        return precio.precio_oportunidad if precio else None


@admin.register(SenalDemandaProducto)
class SenalDemandaProductoAdmin(admin.ModelAdmin):
    list_display = (
        "producto_fuente", "fuente_web", "score_demanda", "nivel_demanda",
        "cantidad_vendida_visible", "cantidad_resenas", "stock_visible", "fecha_relevamiento",
    )
    list_filter = ("nivel_demanda", "origen_dato", "etiqueta_mas_vendido", "etiqueta_destacado", "etiqueta_tendencia")
    search_fields = ("producto_fuente__titulo_original", "texto_vendidos", "observaciones")


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


@admin.register(DuplicadoIgnorado)
class DuplicadoIgnoradoAdmin(admin.ModelAdmin):
    list_display = ("producto_a", "producto_b", "fecha")
    search_fields = ("producto_a__titulo_original", "producto_b__titulo_original", "motivo")


@admin.register(CandidatoCompra)
class CandidatoCompraAdmin(admin.ModelAdmin):
    list_display = (
        "producto_fuente",
        "estado",
        "precio_compra_estimado",
        "precio_reventa_estimado",
        "margen_estimado",
        "porcentaje_margen_estimado",
        "fecha_actualizacion",
    )
    list_filter = ("estado", "fecha_actualizacion")
    search_fields = ("producto_fuente__titulo_original", "motivo", "notas")


@admin.register(CompraProducto)
class CompraProductoAdmin(admin.ModelAdmin):
    list_display = ("candidato", "producto_fuente", "fecha_compra", "cantidad_comprada", "precio_unitario_compra", "costo_total", "estado")
    list_filter = ("estado", "fecha_compra", "fuente_web")
    search_fields = ("producto_fuente__titulo_original", "proveedor_texto", "comprobante_texto")


@admin.register(PublicacionReventa)
class PublicacionReventaAdmin(admin.ModelAdmin):
    list_display = ("compra", "canal", "fecha_publicacion", "precio_publicado_unitario", "cantidad_publicada", "estado")
    list_filter = ("canal", "estado", "fecha_publicacion")
    search_fields = ("titulo_publicacion", "url_publicacion")


@admin.register(VentaProducto)
class VentaProductoAdmin(admin.ModelAdmin):
    list_display = ("compra", "fecha_venta", "cantidad_vendida", "precio_unitario_venta", "ganancia_neta", "margen_pct", "canal_venta", "estado")
    list_filter = ("canal_venta", "estado", "fecha_venta")
    search_fields = ("comprador_texto", "observaciones")


@admin.register(ResultadoComercialProducto)
class ResultadoComercialProductoAdmin(admin.ModelAdmin):
    list_display = ("candidato", "cantidad_comprada_total", "cantidad_vendida_total", "ganancia_neta_total", "margen_real_pct", "estado_resultado")
    list_filter = ("estado_resultado",)
    search_fields = ("candidato__motivo_candidato", "producto_fuente__titulo_original")


@admin.register(OportunidadRadar)
class OportunidadRadarAdmin(admin.ModelAdmin):
    list_display = (
        "id", "fecha_detectada", "tienda", "producto_nombre", "precio_actual",
        "precio_comparable_minimo", "descuento_real_pct_estimado", "score_radar",
        "nivel_oportunidad", "decision_sugerida", "estado",
    )
    list_filter = ("tienda", "nivel_oportunidad", "decision_sugerida", "estado", "requiere_revision", "origen")
    search_fields = ("producto_nombre", "tienda", "motivo_conveniencia", "texto_original")


@admin.register(ImportacionRadarTexto)
class ImportacionRadarTextoAdmin(admin.ModelAdmin):
    list_display = ("id", "titulo", "origen", "estado", "oportunidades_detectadas", "oportunidades_importadas", "errores", "fecha_creacion")
    list_filter = ("origen", "estado")
    search_fields = ("titulo", "texto_original", "resumen")


@admin.register(ComparacionPrecio)
class ComparacionPrecioAdmin(admin.ModelAdmin):
    list_display = ("producto_canonico", "precio_minimo", "precio_promedio", "precio_maximo", "cantidad_fuentes", "fecha_calculo")
    list_filter = ("fecha_calculo", "fuente_mas_barata")
    search_fields = ("producto_canonico__nombre_normalizado",)


@admin.register(SugerenciaMatchingProducto)
class SugerenciaMatchingProductoAdmin(admin.ModelAdmin):
    list_display = ("producto_a", "producto_b", "score", "nivel", "estado", "fecha_creacion")
    list_filter = ("nivel", "estado")
    search_fields = ("producto_a__titulo_original", "producto_b__titulo_original")


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
