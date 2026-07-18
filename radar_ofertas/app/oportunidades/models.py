from decimal import Decimal
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from oportunidades.services.dominios_service import normalizar_dominio, url_pertenece_a_dominio


class FuenteProducto(models.Model):
    TIPO_MARKETPLACE = "marketplace"
    TIPO_TIENDA = "tienda"
    TIPO_MANUAL = "manual"
    TIPO_CHOICES = [
        (TIPO_MARKETPLACE, "Marketplace"),
        (TIPO_TIENDA, "Tienda"),
        (TIPO_MANUAL, "Manual"),
    ]

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    url_base = models.URLField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "fuente de producto"
        verbose_name_plural = "fuentes de producto"

    def __str__(self):
        return self.nombre


class CategoriaInteres(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True, db_index=True)
    palabra_clave = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    prioridad = models.PositiveIntegerField(default=1)
    categoria_padre = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategorias",
    )
    palabras_clave = models.TextField(blank=True, null=True)
    marcas_clave = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "categoria de interes"
        verbose_name_plural = "categorias de interes"
        ordering = ["prioridad", "nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug and self.nombre:
            self.slug = slugify(self.nombre)
        if not self.palabra_clave and self.nombre:
            self.palabra_clave = self.nombre.lower()
        super().save(*args, **kwargs)


CategoriaProducto = CategoriaInteres


class Producto(models.Model):
    CONDICION_NUEVO = "nuevo"
    CONDICION_USADO = "usado"
    CONDICION_REACONDICIONADO = "reacondicionado"
    CONDICION_DESCONOCIDO = "desconocido"
    CONDICION_CHOICES = [
        (CONDICION_NUEVO, "Nuevo"),
        (CONDICION_USADO, "Usado"),
        (CONDICION_REACONDICIONADO, "Reacondicionado"),
        (CONDICION_DESCONOCIDO, "Desconocido"),
    ]

    fuente = models.ForeignKey(FuenteProducto, on_delete=models.PROTECT)
    codigo_externo = models.CharField(max_length=100, blank=True, null=True)
    titulo = models.CharField(max_length=255)
    url = models.URLField()
    marca = models.CharField(max_length=100, blank=True, null=True)
    categoria = models.ForeignKey(CategoriaInteres, on_delete=models.PROTECT)
    categoria_original = models.CharField(max_length=255, blank=True, null=True)
    subcategoria_original = models.CharField(max_length=255, blank=True, null=True)
    etiquetas = models.TextField(blank=True, null=True)
    vendedor = models.CharField(max_length=150, blank=True, null=True)
    reputacion_vendedor = models.CharField(max_length=100, blank=True, null=True)
    condicion = models.CharField(max_length=50, choices=CONDICION_CHOICES)
    es_chico_liviano = models.BooleanField(default=False)
    es_fragil = models.BooleanField(default=False)
    thumbnail_url = models.URLField(blank=True, null=True)
    cantidad_vendida = models.PositiveIntegerField(default=0)
    disponible = models.BooleanField(default=True)
    raw_data = models.TextField(blank=True, null=True)
    url_afiliado = models.URLField(blank=True, null=True)
    afiliado_activo = models.BooleanField(default=False)
    nota_afiliado = models.TextField(blank=True, null=True)
    fecha_alta = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_alta"]

    def __str__(self):
        return self.titulo


class ConsultaMercadoLibre(models.Model):
    categoria = models.ForeignKey(CategoriaInteres, null=True, blank=True, on_delete=models.SET_NULL)
    query = models.CharField(max_length=255)
    site_id = models.CharField(max_length=10, default="MLA")
    limit = models.PositiveIntegerField(default=20)
    offset = models.PositiveIntegerField(default=0)
    cantidad_resultados = models.PositiveIntegerField(default=0)
    exitosa = models.BooleanField(default=False)
    status_code = models.PositiveIntegerField(blank=True, null=True)
    requiere_token = models.BooleanField(default=False)
    forbidden = models.BooleanField(default=False)
    uso_token = models.BooleanField(default=False)
    mensaje_error = models.TextField(blank=True, null=True)
    fecha_consulta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "consulta de Mercado Libre"
        verbose_name_plural = "consultas de Mercado Libre"
        ordering = ["-fecha_consulta"]

    def __str__(self):
        return f"{self.query} ({self.site_id})"


class MercadoLibreToken(models.Model):
    user_id_meli = models.CharField(max_length=100, blank=True, null=True)
    nickname = models.CharField(max_length=150, blank=True, null=True)
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    token_type = models.CharField(max_length=50, blank=True, null=True)
    scope = models.TextField(blank=True, null=True)
    expires_in = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "token de Mercado Libre"
        verbose_name_plural = "tokens de Mercado Libre"
        ordering = ["-fecha_actualizacion"]

    def __str__(self):
        return self.nickname or self.user_id_meli or "Token Mercado Libre"


class FuenteWeb(models.Model):
    TIPO_MARKETPLACE = "marketplace"
    TIPO_TIENDA_ONLINE = "tienda_online"
    TIPO_MAYORISTA = "mayorista"
    TIPO_CATALOGO_PDF = "catalogo_pdf"
    TIPO_EXCEL_CSV = "excel_csv"
    TIPO_AFILIADOS = "afiliados"
    TIPO_MANUAL_ASISTIDA = "manual_asistida"
    TIPO_API_OFICIAL = "api_oficial"
    TIPO_SUPERMERCADO_FISICO = "supermercado_fisico"
    TIPO_DISTRIBUIDORA = "distribuidora"
    TIPO_ALMACEN = "almacen"
    TIPO_CARNICERIA = "carniceria"
    TIPO_POLLERIA = "polleria"
    TIPO_FERIA = "feria"
    TIPO_MERCADO = "mercado"
    TIPO_OFERTA_GONDOLA = "oferta_gondola"
    TIPO_FOLLETO = "folleto"
    TIPO_LISTA_PRECIOS = "lista_precios"
    TIPO_CAPTURA_MANUAL = "captura_manual"
    TIPO_OTRA = "otra"
    TIPO_CHOICES = [
        (TIPO_MARKETPLACE, "Marketplace"),
        (TIPO_TIENDA_ONLINE, "Tienda online"),
        (TIPO_MAYORISTA, "Mayorista"),
        (TIPO_CATALOGO_PDF, "Catalogo PDF"),
        (TIPO_EXCEL_CSV, "Excel/CSV"),
        (TIPO_AFILIADOS, "Afiliados"),
        (TIPO_MANUAL_ASISTIDA, "Manual asistida"),
        (TIPO_API_OFICIAL, "API oficial"),
        (TIPO_SUPERMERCADO_FISICO, "Supermercado fisico"),
        (TIPO_DISTRIBUIDORA, "Distribuidora"),
        (TIPO_ALMACEN, "Almacen"),
        (TIPO_CARNICERIA, "Carniceria"),
        (TIPO_POLLERIA, "Polleria"),
        (TIPO_FERIA, "Feria"),
        (TIPO_MERCADO, "Mercado"),
        (TIPO_OFERTA_GONDOLA, "Oferta de gondola"),
        (TIPO_FOLLETO, "Folleto"),
        (TIPO_LISTA_PRECIOS, "Lista de precios"),
        (TIPO_CAPTURA_MANUAL, "Captura manual"),
        (TIPO_OTRA, "Otra"),
    ]

    nombre = models.CharField(max_length=150)
    url_base = models.URLField()
    tipo_fuente = models.CharField(max_length=30, choices=TIPO_CHOICES)
    rubro_principal = models.CharField(max_length=150, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    prioridad = models.PositiveIntegerField(default=1)
    pais = models.CharField(max_length=80, default="Argentina")
    moneda_principal = models.CharField(max_length=10, default="ARS")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "fuente web"
        verbose_name_plural = "fuentes web"
        ordering = ["prioridad", "nombre"]

    def __str__(self):
        return self.nombre


class PoliticaExtraccionFuente(models.Model):
    SEMAFORO_VERDE = "verde"
    SEMAFORO_AMARILLO = "amarillo"
    SEMAFORO_ROJO = "rojo"
    SEMAFORO_DESCONOCIDO = "desconocido"
    SEMAFORO_CHOICES = [
        (SEMAFORO_VERDE, "Verde"),
        (SEMAFORO_AMARILLO, "Amarillo"),
        (SEMAFORO_ROJO, "Rojo"),
        (SEMAFORO_DESCONOCIDO, "Desconocido"),
    ]

    METODO_API_OFICIAL = "api_oficial"
    METODO_CSV_EXCEL = "csv_excel"
    METODO_CATALOGO_PDF = "catalogo_pdf"
    METODO_SCRAPING_PERMITIDO = "scraping_permitido"
    METODO_CARGA_URL = "carga_url"
    METODO_CARGA_MANUAL = "carga_manual"
    METODO_NO_PERMITIDO = "no_permitido"
    METODO_PENDIENTE_REVISION = "pendiente_revision"
    METODO_CHOICES = [
        (METODO_API_OFICIAL, "API oficial"),
        (METODO_CSV_EXCEL, "CSV/Excel"),
        (METODO_CATALOGO_PDF, "Catalogo PDF"),
        (METODO_SCRAPING_PERMITIDO, "Scraping permitido"),
        (METODO_CARGA_URL, "Carga por URL"),
        (METODO_CARGA_MANUAL, "Carga manual"),
        (METODO_NO_PERMITIDO, "No permitido"),
        (METODO_PENDIENTE_REVISION, "Pendiente revision"),
    ]

    RIESGO_BAJO = "bajo"
    RIESGO_MEDIO = "medio"
    RIESGO_ALTO = "alto"
    RIESGO_DESCONOCIDO = "desconocido"
    RIESGO_CHOICES = [
        (RIESGO_BAJO, "Bajo"),
        (RIESGO_MEDIO, "Medio"),
        (RIESGO_ALTO, "Alto"),
        (RIESGO_DESCONOCIDO, "Desconocido"),
    ]

    fuente = models.OneToOneField(FuenteWeb, on_delete=models.CASCADE, related_name="politica_extraccion")
    semaforo = models.CharField(max_length=20, choices=SEMAFORO_CHOICES, default=SEMAFORO_DESCONOCIDO)
    metodo_preferido = models.CharField(max_length=30, choices=METODO_CHOICES, default=METODO_PENDIENTE_REVISION)
    permite_scraping = models.BooleanField(default=False)
    requiere_login = models.BooleanField(default=False)
    tiene_captcha = models.BooleanField(default=False)
    tiene_api = models.BooleanField(default=False)
    tiene_afiliados = models.BooleanField(default=False)
    robots_txt_url = models.URLField(blank=True, null=True)
    robots_txt_revisado = models.BooleanField(default=False)
    terminos_revisados = models.BooleanField(default=False)
    frecuencia_sugerida = models.CharField(max_length=100, blank=True, null=True)
    riesgo_tecnico = models.CharField(max_length=20, choices=RIESGO_CHOICES, default=RIESGO_DESCONOCIDO)
    riesgo_legal = models.CharField(max_length=20, choices=RIESGO_CHOICES, default=RIESGO_DESCONOCIDO)
    observaciones = models.TextField(blank=True, null=True)
    fecha_revision = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "politica de extraccion"
        verbose_name_plural = "politicas de extraccion"

    def __str__(self):
        return f"{self.fuente} - {self.semaforo}"


class CategoriaFuente(models.Model):
    fuente = models.ForeignKey(FuenteWeb, on_delete=models.CASCADE, related_name="categorias_fuente")
    nombre = models.CharField(max_length=150)
    url_categoria = models.URLField(blank=True, null=True)
    categoria_normalizada = models.ForeignKey(CategoriaInteres, on_delete=models.SET_NULL, null=True, blank=True)
    activa = models.BooleanField(default=True)
    prioridad = models.PositiveIntegerField(default=1)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "categoria de fuente"
        verbose_name_plural = "categorias de fuente"
        ordering = ["fuente", "prioridad", "nombre"]

    def __str__(self):
        return f"{self.fuente} - {self.nombre}"


class ProductoCanonico(models.Model):
    nombre_normalizado = models.CharField(max_length=255)
    categoria = models.ForeignKey(CategoriaInteres, on_delete=models.PROTECT)
    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    descripcion_normalizada = models.TextField(blank=True, null=True)
    atributos_clave = models.TextField(blank=True, null=True)
    es_chico_liviano = models.BooleanField(default=False)
    es_fragil = models.BooleanField(default=False)
    estacionalidad = models.CharField(max_length=150, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "producto canonico"
        verbose_name_plural = "productos canonicos"
        ordering = ["nombre_normalizado"]

    def __str__(self):
        return self.nombre_normalizado


class ProductoFuente(models.Model):
    lote_origen = models.ForeignKey(
        "LoteCaptura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos_origen",
    )
    producto_canonico = models.ForeignKey(
        ProductoCanonico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="apariciones",
    )
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.PROTECT, related_name="productos_fuente")
    categoria_fuente = models.ForeignKey(CategoriaFuente, on_delete=models.SET_NULL, null=True, blank=True)
    categoria_original = models.CharField(max_length=255, blank=True, null=True)
    subcategoria_original = models.CharField(max_length=255, blank=True, null=True)
    etiquetas = models.TextField(blank=True, null=True)
    codigo_externo = models.CharField(max_length=150, blank=True, null=True)
    titulo_original = models.CharField(max_length=255)
    url_producto = models.URLField()
    imagen_url = models.URLField(blank=True, null=True)
    marca_detectada = models.CharField(max_length=100, blank=True, null=True)
    descripcion_original = models.TextField(blank=True, null=True)
    vendedor = models.CharField(max_length=150, blank=True, null=True)
    condicion = models.CharField(max_length=50, choices=Producto.CONDICION_CHOICES)
    disponible = models.BooleanField(default=True)
    stock_texto = models.CharField(max_length=150, blank=True, null=True)
    raw_data = models.TextField(blank=True, null=True)
    requiere_revision = models.BooleanField(default=False)
    revisado = models.BooleanField(default=False)
    motivo_revision = models.TextField(blank=True, null=True)
    url_tecnica_generada = models.BooleanField(default=False)
    hash_origen = models.CharField(max_length=100, blank=True, null=True)
    fecha_revision = models.DateTimeField(blank=True, null=True)
    score_comercial = models.PositiveIntegerField(default=0)
    DEMANDA_ALTA = "alta"
    DEMANDA_MEDIA = "media"
    DEMANDA_BAJA = "baja"
    DEMANDA_DESCONOCIDA = "desconocida"
    DEMANDA_CHOICES = [
        (DEMANDA_ALTA, "Alta"),
        (DEMANDA_MEDIA, "Media"),
        (DEMANDA_BAJA, "Baja"),
        (DEMANDA_DESCONOCIDA, "Desconocida"),
    ]
    score_demanda_actual = models.PositiveIntegerField(default=0)
    nivel_demanda_actual = models.CharField(max_length=20, choices=DEMANDA_CHOICES, default=DEMANDA_DESCONOCIDA)
    motivo_demanda_actual = models.TextField(blank=True, null=True)
    fecha_demanda_actual = models.DateTimeField(blank=True, null=True)
    NIVEL_ALTO = "alto"
    NIVEL_MEDIO = "medio"
    NIVEL_BAJO = "bajo"
    NIVEL_REVISAR = "revisar"
    NIVEL_DESCONOCIDO = "desconocido"
    NIVEL_CHOICES = [
        (NIVEL_ALTO, "Alto"),
        (NIVEL_MEDIO, "Medio"),
        (NIVEL_BAJO, "Bajo"),
        (NIVEL_REVISAR, "Revisar"),
        (NIVEL_DESCONOCIDO, "Desconocido"),
    ]
    nivel_oportunidad = models.CharField(max_length=20, choices=NIVEL_CHOICES, default=NIVEL_DESCONOCIDO)
    motivo_score_comercial = models.TextField(blank=True, null=True)
    fecha_score_comercial = models.DateTimeField(blank=True, null=True)
    nota_curaduria = models.TextField(blank=True, null=True)
    fecha_ultima_curaduria = models.DateTimeField(blank=True, null=True)
    fusionado_en = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos_fusionados",
    )
    descartado_curaduria = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "producto por fuente"
        verbose_name_plural = "productos por fuente"
        ordering = ["-fecha_actualizacion"]

    def __str__(self):
        return self.titulo_original


class SenalDemandaProducto(models.Model):
    ORIGEN_DIRECTO = "directo"
    ORIGEN_ESTIMADO = "estimado"
    ORIGEN_MANUAL = "manual"
    ORIGEN_CALCULADO = "calculado"
    ORIGEN_CHOICES = [
        (ORIGEN_DIRECTO, "Directo"),
        (ORIGEN_ESTIMADO, "Estimado"),
        (ORIGEN_MANUAL, "Manual"),
        (ORIGEN_CALCULADO, "Calculado"),
    ]

    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.CASCADE, related_name="senales_demanda")
    lote_captura = models.ForeignKey(
        "LoteCaptura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="senales_demanda",
    )
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.PROTECT, null=True, blank=True)
    fecha_relevamiento = models.DateTimeField(auto_now_add=True)
    cantidad_vendida_visible = models.PositiveIntegerField(default=0)
    texto_vendidos = models.CharField(max_length=200, blank=True, null=True)
    cantidad_resenas = models.PositiveIntegerField(default=0)
    cantidad_preguntas = models.PositiveIntegerField(default=0)
    calificacion = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    etiqueta_mas_vendido = models.BooleanField(default=False)
    etiqueta_destacado = models.BooleanField(default=False)
    etiqueta_tendencia = models.BooleanField(default=False)
    ranking_categoria = models.PositiveIntegerField(default=0)
    stock_visible = models.PositiveIntegerField(default=0)
    stock_anterior = models.PositiveIntegerField(default=0)
    variacion_stock = models.IntegerField(default=0)
    texto_stock = models.CharField(max_length=200, blank=True, null=True)
    aparece_en_destacados = models.BooleanField(default=False)
    aparece_en_promociones = models.BooleanField(default=False)
    aparece_en_varias_fuentes = models.BooleanField(default=False)
    cantidad_fuentes_donde_aparece = models.PositiveIntegerField(default=0)
    recurrencia_en_previews = models.PositiveIntegerField(default=0)
    score_demanda = models.PositiveIntegerField(default=0)
    nivel_demanda = models.CharField(max_length=20, choices=ProductoFuente.DEMANDA_CHOICES, default=ProductoFuente.DEMANDA_DESCONOCIDA)
    motivo_demanda = models.TextField(blank=True, null=True)
    origen_dato = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default=ORIGEN_ESTIMADO)
    requiere_revision = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "senal de demanda de producto"
        verbose_name_plural = "senales de demanda de productos"
        ordering = ["-fecha_relevamiento", "-id"]

    def __str__(self):
        return f"{self.producto_fuente} - {self.nivel_demanda} ({self.score_demanda})"


class OperacionCuraduria(models.Model):
    TIPO_REVISAR = "revisar"
    TIPO_CORREGIR = "corregir"
    TIPO_FUSIONAR = "fusionar"
    TIPO_DESVINCULAR = "desvincular"
    TIPO_REASIGNAR = "reasignar"
    TIPO_RECALCULAR = "recalcular"
    TIPO_ELIMINAR = "eliminar"
    TIPO_IMPORTAR = "importar"
    TIPO_EXPORTAR = "exportar"
    TIPO_CHOICES = [
        (TIPO_REVISAR, "Revisar"),
        (TIPO_CORREGIR, "Corregir"),
        (TIPO_FUSIONAR, "Fusionar"),
        (TIPO_DESVINCULAR, "Desvincular"),
        (TIPO_REASIGNAR, "Reasignar"),
        (TIPO_RECALCULAR, "Recalcular"),
        (TIPO_ELIMINAR, "Eliminar"),
        (TIPO_IMPORTAR, "Importar"),
        (TIPO_EXPORTAR, "Exportar"),
    ]

    tipo_operacion = models.CharField(max_length=30, choices=TIPO_CHOICES)
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True)
    descripcion = models.TextField()
    datos_antes = models.TextField(blank=True, null=True)
    datos_despues = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario_texto = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        verbose_name = "operacion de curaduria"
        verbose_name_plural = "operaciones de curaduria"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo_operacion} - {self.fecha:%Y-%m-%d %H:%M}"


class DuplicadoIgnorado(models.Model):
    producto_a = models.ForeignKey(ProductoFuente, on_delete=models.CASCADE, related_name="duplicados_ignorados_a")
    producto_b = models.ForeignKey(ProductoFuente, on_delete=models.CASCADE, related_name="duplicados_ignorados_b")
    motivo = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "duplicado ignorado"
        verbose_name_plural = "duplicados ignorados"
        unique_together = ("producto_a", "producto_b")
        ordering = ["-fecha"]

    def __str__(self):
        return f"Ignorado #{self.producto_a_id} / #{self.producto_b_id}"


class CandidatoCompra(models.Model):
    ESTADO_OBSERVADO = "observado"
    ESTADO_CANDIDATO = "candidato"
    ESTADO_APROBADO_COMPRA = "aprobado_compra"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_COMPRADO = "comprado"
    ESTADO_PUBLICADO = "publicado"
    ESTADO_VENDIDO_PARCIAL = "vendido_parcial"
    ESTADO_VENDIDO_TOTAL = "vendido_total"
    ESTADO_CANCELADO = "cancelado"
    ESTADO_PERDIDO = "perdido"
    ESTADO_CHOICES = [
        (ESTADO_OBSERVADO, "Observado"),
        (ESTADO_CANDIDATO, "Candidato"),
        (ESTADO_APROBADO_COMPRA, "Aprobado para compra"),
        (ESTADO_DESCARTADO, "Descartado"),
        (ESTADO_COMPRADO, "Comprado"),
        (ESTADO_PUBLICADO, "Publicado"),
        (ESTADO_VENDIDO_PARCIAL, "Vendido parcial"),
        (ESTADO_VENDIDO_TOTAL, "Vendido total"),
        (ESTADO_CANCELADO, "Cancelado"),
        (ESTADO_PERDIDO, "Perdido"),
    ]
    PRIORIDAD_ALTA = "alta"
    PRIORIDAD_MEDIA = "media"
    PRIORIDAD_BAJA = "baja"
    PRIORIDAD_CHOICES = [(PRIORIDAD_ALTA, "Alta"), (PRIORIDAD_MEDIA, "Media"), (PRIORIDAD_BAJA, "Baja")]
    ORIGEN_RANKING = "ranking"
    ORIGEN_RADAR_TEXTO = "radar_texto"
    ORIGEN_MANUAL = "manual"
    ORIGEN_CHOICES = [
        (ORIGEN_RANKING, "Ranking"),
        (ORIGEN_RADAR_TEXTO, "Radar texto"),
        (ORIGEN_MANUAL, "Manual"),
    ]

    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True, related_name="candidaturas_compra")
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True, related_name="candidaturas_compra")
    lote_captura = models.ForeignKey("LoteCaptura", on_delete=models.SET_NULL, null=True, blank=True, related_name="candidaturas_compra")
    producto_texto = models.CharField(max_length=250, blank=True, null=True)
    tienda_texto = models.CharField(max_length=150, blank=True, null=True)
    origen_candidato = models.CharField(max_length=30, choices=ORIGEN_CHOICES, default=ORIGEN_RANKING)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_CANDIDATO)
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default=PRIORIDAD_MEDIA)
    precio_oportunidad_detectado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fuente_precio = models.CharField(max_length=100, blank=True, null=True)
    score_comercial_detectado = models.PositiveIntegerField(default=0)
    score_demanda_detectado = models.PositiveIntegerField(default=0)
    motivo_candidato = models.TextField(blank=True, null=True)
    precio_compra_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_reventa_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    porcentaje_margen_estimado = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    motivo = models.TextField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    fecha_deteccion = models.DateTimeField(auto_now_add=True, null=True)
    fecha_decision = models.DateTimeField(null=True, blank=True)
    motivo_descarte = models.TextField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "candidato de compra"
        verbose_name_plural = "candidatos de compra"
        ordering = ["-fecha_actualizacion"]

    def __str__(self):
        return f"{self.producto_fuente or self.producto_canonico or self.producto_texto or 'Candidato'} - {self.estado}"


class ImportacionRadarTexto(models.Model):
    ORIGEN_CHATGPT_RADAR = "chatgpt_radar"
    ORIGEN_TEXTO_EXTERNO = "texto_externo"
    ORIGEN_MANUAL = "manual"
    ORIGEN_CHOICES = [
        (ORIGEN_CHATGPT_RADAR, "ChatGPT Radar"),
        (ORIGEN_TEXTO_EXTERNO, "Texto externo"),
        (ORIGEN_MANUAL, "Manual"),
    ]
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_ANALIZADA = "analizada"
    ESTADO_IMPORTADA = "importada"
    ESTADO_IMPORTADA_CON_ADVERTENCIAS = "importada_con_advertencias"
    ESTADO_ERROR = "error"
    ESTADO_DESCARTADA = "descartada"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ANALIZADA, "Analizada"),
        (ESTADO_IMPORTADA, "Importada"),
        (ESTADO_IMPORTADA_CON_ADVERTENCIAS, "Importada con advertencias"),
        (ESTADO_ERROR, "Error"),
        (ESTADO_DESCARTADA, "Descartada"),
    ]

    titulo = models.CharField(max_length=200)
    texto_original = models.TextField()
    origen = models.CharField(max_length=30, choices=ORIGEN_CHOICES, default=ORIGEN_CHATGPT_RADAR)
    estado = models.CharField(max_length=40, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    oportunidades_detectadas = models.PositiveIntegerField(default=0)
    oportunidades_importadas = models.PositiveIntegerField(default=0)
    errores = models.PositiveIntegerField(default=0)
    resumen = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "importacion radar texto"
        verbose_name_plural = "importaciones radar texto"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.titulo


class OportunidadRadar(models.Model):
    DECISION_COMPRAR = "comprar"
    DECISION_ANALIZAR = "analizar"
    DECISION_ESPERAR = "esperar"
    DECISION_DESCARTAR = "descartar"
    DECISION_CHOICES = [
        (DECISION_COMPRAR, "Comprar"),
        (DECISION_ANALIZAR, "Analizar"),
        (DECISION_ESPERAR, "Esperar"),
        (DECISION_DESCARTAR, "Descartar"),
    ]
    NIVEL_ALTA = "alta"
    NIVEL_MEDIA = "media"
    NIVEL_BAJA = "baja"
    NIVEL_DUDOSA = "dudosa"
    NIVEL_CHOICES = [
        (NIVEL_ALTA, "Alta"),
        (NIVEL_MEDIA, "Media"),
        (NIVEL_BAJA, "Baja"),
        (NIVEL_DUDOSA, "Dudosa"),
    ]
    ORIGEN_CHATGPT_RADAR = "chatgpt_radar"
    ORIGEN_MANUAL = "manual"
    ORIGEN_TEXTO_EXTERNO = "texto_externo"
    ORIGEN_OTRO = "otro"
    ORIGEN_CHOICES = [
        (ORIGEN_CHATGPT_RADAR, "ChatGPT Radar"),
        (ORIGEN_MANUAL, "Manual"),
        (ORIGEN_TEXTO_EXTERNO, "Texto externo"),
        (ORIGEN_OTRO, "Otro"),
    ]
    ESTADO_DETECTADA = "detectada"
    ESTADO_IMPORTADA = "importada"
    ESTADO_REVISADA = "revisada"
    ESTADO_VINCULADA = "vinculada"
    ESTADO_CANDIDATA = "candidata"
    ESTADO_DESCARTADA = "descartada"
    ESTADO_CHOICES = [
        (ESTADO_DETECTADA, "Detectada"),
        (ESTADO_IMPORTADA, "Importada"),
        (ESTADO_REVISADA, "Revisada"),
        (ESTADO_VINCULADA, "Vinculada"),
        (ESTADO_CANDIDATA, "Candidata"),
        (ESTADO_DESCARTADA, "Descartada"),
    ]

    importacion = models.ForeignKey(ImportacionRadarTexto, on_delete=models.SET_NULL, null=True, blank=True, related_name="oportunidades")
    titulo = models.CharField(max_length=250)
    tienda = models.CharField(max_length=150, blank=True, null=True)
    producto_nombre = models.CharField(max_length=250)
    marca = models.CharField(max_length=150, blank=True, null=True)
    modelo = models.CharField(max_length=150, blank=True, null=True)
    categoria_texto = models.CharField(max_length=150, blank=True, null=True)
    rubro = models.CharField(max_length=150, blank=True, null=True)
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True, related_name="oportunidades_radar")
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True, related_name="oportunidades_radar")
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.SET_NULL, null=True, blank=True, related_name="oportunidades_radar")
    candidato_compra = models.ForeignKey(CandidatoCompra, on_delete=models.SET_NULL, null=True, blank=True, related_name="oportunidades_radar")
    precio_actual = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    precio_comparable_minimo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    precio_comparable_maximo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    precio_historico_referencia = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    descuento_real_pct_estimado = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    descuento_texto = models.CharField(max_length=200, blank=True, null=True)
    precio_lista = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    precio_transferencia_contado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    precio_tarjeta_cuotas = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cuotas_texto = models.CharField(max_length=200, blank=True, null=True)
    comparable_principal_tienda = models.CharField(max_length=150, blank=True, null=True)
    comparable_principal_precio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    comparables_texto = models.TextField(blank=True, null=True)
    envio_texto = models.CharField(max_length=250, blank=True, null=True)
    stock_texto = models.CharField(max_length=250, blank=True, null=True)
    vendedor_texto = models.CharField(max_length=250, blank=True, null=True)
    ubicacion_texto = models.CharField(max_length=250, blank=True, null=True)
    motivo_conveniencia = models.TextField(blank=True, null=True)
    chequeo_antimarketing = models.TextField(blank=True, null=True)
    riesgo_texto = models.TextField(blank=True, null=True)
    decision_sugerida = models.CharField(max_length=20, choices=DECISION_CHOICES, default=DECISION_ANALIZAR)
    score_radar = models.PositiveIntegerField(default=0)
    nivel_oportunidad = models.CharField(max_length=20, choices=NIVEL_CHOICES, default=NIVEL_DUDOSA)
    requiere_revision = models.BooleanField(default=True)
    origen = models.CharField(max_length=30, choices=ORIGEN_CHOICES, default=ORIGEN_CHATGPT_RADAR)
    texto_original = models.TextField()
    texto_parseado = models.TextField(blank=True, null=True)
    url_oferta = models.URLField(blank=True, null=True)
    url_comparable = models.URLField(blank=True, null=True)
    fecha_detectada = models.DateTimeField(auto_now_add=True)
    fecha_oferta_texto = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_IMPORTADA)
    apta_dataset = models.BooleanField(default=True)
    excluir_ml = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "oportunidad radar"
        verbose_name_plural = "oportunidades radar"
        ordering = ["-fecha_detectada", "-score_radar"]

    def __str__(self):
        return self.titulo


class PrecioFuente(models.Model):
    ORIGEN_API = "api"
    ORIGEN_SCRAPING = "scraping"
    ORIGEN_CSV_EXCEL = "csv_excel"
    ORIGEN_PDF = "pdf"
    ORIGEN_MANUAL = "manual"
    ORIGEN_URL_ASISTIDA = "url_asistida"
    ORIGEN_OTRO = "otro"
    ORIGEN_CHOICES = [
        (ORIGEN_API, "API"),
        (ORIGEN_SCRAPING, "Scraping"),
        (ORIGEN_CSV_EXCEL, "CSV/Excel"),
        (ORIGEN_PDF, "PDF"),
        (ORIGEN_MANUAL, "Manual"),
        (ORIGEN_URL_ASISTIDA, "URL asistida"),
        (ORIGEN_OTRO, "Otro"),
    ]
    TIPO_PRECIO_LISTA = "lista"
    TIPO_PRECIO_TRANSFERENCIA = "transferencia"
    TIPO_PRECIO_TARJETA = "tarjeta"
    TIPO_PRECIO_DESCONOCIDO = "desconocido"
    TIPO_PRECIO_CHOICES = [
        (TIPO_PRECIO_LISTA, "Lista"),
        (TIPO_PRECIO_TRANSFERENCIA, "Transferencia"),
        (TIPO_PRECIO_TARJETA, "Tarjeta"),
        (TIPO_PRECIO_DESCONOCIDO, "Desconocido"),
    ]

    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.CASCADE, related_name="precios_fuente")
    lote_captura = models.ForeignKey(
        "LoteCaptura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="precios",
    )
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    precio_lista = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_transferencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_tarjeta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cuotas_texto = models.CharField(max_length=200, blank=True, null=True)
    precio_oportunidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tipo_precio_oportunidad = models.CharField(
        max_length=20,
        choices=TIPO_PRECIO_CHOICES,
        default=TIPO_PRECIO_DESCONOCIDO,
    )
    descuento_porcentaje = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    costo_envio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    moneda = models.CharField(max_length=10, default="ARS")
    fecha_relevamiento = models.DateTimeField(auto_now_add=True)
    origen_dato = models.CharField(max_length=20, choices=ORIGEN_CHOICES)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "precio por fuente"
        verbose_name_plural = "precios por fuente"
        ordering = ["-fecha_relevamiento"]

    def __str__(self):
        return f"{self.producto_fuente} - {self.moneda} {self.precio}"


class LoteRanking(models.Model):
    TIPO_ALTA_VENTA = "alta_venta"
    TIPO_OBRA_HOGAR = "obra_hogar"
    TIPO_SUPERMERCADO_CONSUMO = "supermercado_consumo"
    TIPO_SUPERMERCADO_REVENTA = "supermercado_reventa"
    TIPO_CHOICES = [
        (TIPO_ALTA_VENTA, "Productos con senales de alta venta"),
        (TIPO_OBRA_HOGAR, "Ofertas de obra/hogar"),
        (TIPO_SUPERMERCADO_CONSUMO, "Supermercado/consumo"),
        (TIPO_SUPERMERCADO_REVENTA, "Supermercado/reventa"),
    ]

    ESTADO_BORRADOR = "borrador"
    ESTADO_VALIDADO = "validado"
    ESTADO_PUBLICADO = "publicado"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_VALIDADO, "Validado"),
        (ESTADO_PUBLICADO, "Publicado"),
        (ESTADO_DESCARTADO, "Descartado"),
    ]

    nombre = models.CharField(max_length=180)
    tipo_ranking = models.CharField(max_length=40, choices=TIPO_CHOICES, default=TIPO_ALTA_VENTA)
    alcance = models.CharField(max_length=150, blank=True, null=True)
    categoria = models.ForeignKey(CategoriaInteres, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes_ranking")
    fecha_referencia = models.DateField()
    fecha_importacion = models.DateTimeField(auto_now_add=True)
    origen = models.CharField(max_length=180, default="Radar ChatGPT - carga manual")
    metodologia = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad_filas = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    hash_importacion = models.CharField(max_length=64, db_index=True)
    texto_original = models.TextField(blank=True, null=True)
    posible_duplicado = models.BooleanField(default=False)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "lote de ranking"
        verbose_name_plural = "lotes de ranking"
        ordering = ["-fecha_referencia", "-fecha_importacion"]
        indexes = [
            models.Index(fields=["tipo_ranking", "alcance", "fecha_referencia"]),
            models.Index(fields=["estado", "fecha_referencia"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.fecha_referencia})"


class ItemRanking(models.Model):
    SENAL_ETIQUETA_MAS_VENDIDO = "etiqueta_mas_vendido"
    SENAL_RANKING_OFICIAL = "ranking_oficial"
    SENAL_BLOQUE_DESTACADO = "bloque_destacado"
    SENAL_BUSQUEDA_DESTACADA = "busqueda_destacada"
    SENAL_ALTA_RECURRENCIA = "alta_recurrencia"
    SENAL_RADAR_CHATGPT = "radar_chatgpt"
    SENAL_CARGA_MANUAL = "carga_manual"
    SENAL_OTRA = "otra"
    SENAL_CHOICES = [
        (SENAL_ETIQUETA_MAS_VENDIDO, "Etiqueta mas vendido"),
        (SENAL_RANKING_OFICIAL, "Ranking oficial"),
        (SENAL_BLOQUE_DESTACADO, "Bloque destacado"),
        (SENAL_BUSQUEDA_DESTACADA, "Busqueda destacada"),
        (SENAL_ALTA_RECURRENCIA, "Alta recurrencia"),
        (SENAL_RADAR_CHATGPT, "Radar ChatGPT"),
        (SENAL_CARGA_MANUAL, "Carga manual"),
        (SENAL_OTRA, "Otra"),
    ]

    EVIDENCIA_FICHA = "ficha_producto"
    EVIDENCIA_LISTADO = "listado_productos"
    EVIDENCIA_CATEGORIA = "pagina_categoria"
    EVIDENCIA_RANKING_TIENDA = "ranking_tienda"
    EVIDENCIA_FOLLETO = "folleto"
    EVIDENCIA_CATALOGO = "catalogo"
    EVIDENCIA_PDF = "pdf"
    EVIDENCIA_OTRA = "otra"
    EVIDENCIA_CHOICES = [
        (EVIDENCIA_FICHA, "Ficha de producto"),
        (EVIDENCIA_LISTADO, "Listado de productos"),
        (EVIDENCIA_CATEGORIA, "Pagina de categoria"),
        (EVIDENCIA_RANKING_TIENDA, "Ranking de tienda"),
        (EVIDENCIA_FOLLETO, "Folleto"),
        (EVIDENCIA_CATALOGO, "Catalogo"),
        (EVIDENCIA_PDF, "PDF"),
        (EVIDENCIA_OTRA, "Otra"),
    ]

    VERIFICACION_PENDIENTE = "pendiente"
    VERIFICACION_VERIFICADO = "verificado"
    VERIFICACION_INSUFICIENTE = "evidencia_insuficiente"
    VERIFICACION_DESCARTADO = "descartado"
    VERIFICACION_CHOICES = [
        (VERIFICACION_PENDIENTE, "Pendiente"),
        (VERIFICACION_VERIFICADO, "Verificado"),
        (VERIFICACION_INSUFICIENTE, "Evidencia insuficiente"),
        (VERIFICACION_DESCARTADO, "Descartado"),
    ]

    TENDENCIA_NUEVO = "nuevo"
    TENDENCIA_SUBIO = "subio"
    TENDENCIA_BAJO = "bajo"
    TENDENCIA_MANTUVO = "se_mantuvo"
    TENDENCIA_SIN_COMPARACION = "sin_comparacion"
    TENDENCIA_CHOICES = [
        (TENDENCIA_NUEVO, "Nuevo"),
        (TENDENCIA_SUBIO, "Subio"),
        (TENDENCIA_BAJO, "Bajo"),
        (TENDENCIA_MANTUVO, "Se mantuvo"),
        (TENDENCIA_SIN_COMPARACION, "Sin comparacion"),
    ]

    PRESENTACION_INDIVIDUAL = "individual"
    PRESENTACION_PACK = "pack"
    PRESENTACION_FARDO = "fardo"
    PRESENTACION_BULTO = "bulto"
    PRESENTACION_PROMOCION = "promocion"
    PRESENTACION_CHOICES = [
        (PRESENTACION_INDIVIDUAL, "Individual"),
        (PRESENTACION_PACK, "Pack"),
        (PRESENTACION_FARDO, "Fardo"),
        (PRESENTACION_BULTO, "Bulto"),
        (PRESENTACION_PROMOCION, "Promocion"),
    ]

    UNIDAD_ML = "ml"
    UNIDAD_LITRO = "litro"
    UNIDAD_G = "g"
    UNIDAD_KG = "kg"
    UNIDAD_UNIDAD = "unidad"
    UNIDAD_CHOICES = [
        (UNIDAD_ML, "ml"),
        (UNIDAD_LITRO, "litro"),
        (UNIDAD_G, "g"),
        (UNIDAD_KG, "kg"),
        (UNIDAD_UNIDAD, "unidad"),
    ]

    PROMO_NINGUNA = "ninguna"
    PROMO_2X1 = "2x1"
    PROMO_3X2 = "3x2"
    PROMO_SEGUNDA_DESCUENTO = "segunda_descuento"
    PROMO_DESCUENTO_DIRECTO = "descuento_directo"
    PROMO_DESCUENTO_BANCARIO = "descuento_bancario"
    PROMO_TRANSFERENCIA = "transferencia"
    PROMO_TARJETA = "tarjeta"
    PROMO_PERSONALIZADA = "personalizada"
    PROMO_CHOICES = [
        (PROMO_NINGUNA, "Sin promocion"),
        (PROMO_2X1, "2x1"),
        (PROMO_3X2, "3x2"),
        (PROMO_SEGUNDA_DESCUENTO, "Segunda unidad con descuento"),
        (PROMO_DESCUENTO_DIRECTO, "Descuento directo"),
        (PROMO_DESCUENTO_BANCARIO, "Descuento bancario"),
        (PROMO_TRANSFERENCIA, "Transferencia"),
        (PROMO_TARJETA, "Tarjeta"),
        (PROMO_PERSONALIZADA, "Personalizada"),
    ]

    ROTACION_ALTA = "alta"
    ROTACION_MEDIA = "media"
    ROTACION_BAJA = "baja"
    ROTACION_SIN_DETERMINAR = "sin_determinar"
    ROTACION_CHOICES = [
        (ROTACION_ALTA, "Alta"),
        (ROTACION_MEDIA, "Media"),
        (ROTACION_BAJA, "Baja"),
        (ROTACION_SIN_DETERMINAR, "Sin determinar"),
    ]

    CONVENIENCIA_CONSUMO = "consumo_propio"
    CONVENIENCIA_REVENTA = "reventa"
    CONVENIENCIA_AMBAS = "ambas"
    CONVENIENCIA_SIN_DETERMINAR = "sin_determinar"
    CONVENIENCIA_CHOICES = [
        (CONVENIENCIA_CONSUMO, "Conveniente para consumo propio"),
        (CONVENIENCIA_REVENTA, "Posible oportunidad de reventa"),
        (CONVENIENCIA_AMBAS, "Consumo y reventa"),
        (CONVENIENCIA_SIN_DETERMINAR, "Sin determinar"),
    ]

    lote = models.ForeignKey(LoteRanking, on_delete=models.CASCADE, related_name="items")
    posicion = models.PositiveIntegerField()
    nombre_original = models.CharField(max_length=255)
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True, related_name="items_ranking")
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True, related_name="items_ranking")
    categoria = models.ForeignKey(CategoriaInteres, on_delete=models.SET_NULL, null=True, blank=True, related_name="items_ranking")
    subcategoria = models.CharField(max_length=150, blank=True, null=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    tienda = models.CharField(max_length=150, blank=True, null=True)
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.SET_NULL, null=True, blank=True, related_name="items_ranking")
    texto_senal = models.TextField(blank=True, null=True)
    tipo_senal = models.CharField(max_length=40, choices=SENAL_CHOICES, default=SENAL_CARGA_MANUAL)
    url_evidencia = models.URLField(blank=True, null=True)
    tipo_evidencia = models.CharField(max_length=40, choices=EVIDENCIA_CHOICES, default=EVIDENCIA_OTRA)
    fecha_observacion = models.DateField(null=True, blank=True)
    estado_verificacion = models.CharField(max_length=40, choices=VERIFICACION_CHOICES, default=VERIFICACION_PENDIENTE)
    observaciones = models.TextField(blank=True, null=True)
    posicion_anterior = models.PositiveIntegerField(null=True, blank=True)
    variacion_posiciones = models.IntegerField(default=0)
    tendencia = models.CharField(max_length=40, choices=TENDENCIA_CHOICES, default=TENDENCIA_SIN_COMPARACION)
    apariciones_ultimos_lotes = models.PositiveIntegerField(default=1)
    primera_fecha_observada = models.DateField(null=True, blank=True)
    ultima_fecha_observada = models.DateField(null=True, blank=True)
    evidencia_es_ficha_exacta = models.BooleanField(default=False)
    coincidencia_confianza = models.PositiveIntegerField(default=0)
    coincidencia_mensaje = models.CharField(max_length=255, blank=True, null=True)

    tipo_presentacion = models.CharField(max_length=20, choices=PRESENTACION_CHOICES, default=PRESENTACION_INDIVIDUAL)
    unidades_por_presentacion = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    contenido_neto_por_unidad = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    unidad_medida_original = models.CharField(max_length=20, choices=UNIDAD_CHOICES, default=UNIDAD_UNIDAD)
    presentaciones_incluidas = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unidades_totales = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    contenido_total = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    precio_final_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_envio_traslado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_final_puesto_salta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_por_unidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_por_litro = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_por_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_por_metro = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_por_100 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tipo_promocion = models.CharField(max_length=40, choices=PROMO_CHOICES, default=PROMO_NINGUNA)
    cantidad_total_recibida = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_pagada = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_total_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    precio_reventa_referencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_efectivo_por_unidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_bruto_estimado_unidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_porcentual_estimado = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cantidad_minima_bulto = models.CharField(max_length=100, blank=True, null=True)
    limite_por_cliente = models.CharField(max_length=100, blank=True, null=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    rotacion = models.CharField(max_length=30, choices=ROTACION_CHOICES, default=ROTACION_SIN_DETERMINAR)
    conveniencia = models.CharField(max_length=30, choices=CONVENIENCIA_CHOICES, default=CONVENIENCIA_SIN_DETERMINAR)

    raw_data = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "item de ranking"
        verbose_name_plural = "items de ranking"
        ordering = ["lote", "posicion", "id"]
        indexes = [
            models.Index(fields=["lote", "posicion"]),
            models.Index(fields=["tienda", "categoria"]),
            models.Index(fields=["tendencia"]),
        ]

    def __str__(self):
        return f"#{self.posicion} {self.nombre_original}"


class ComparacionPrecio(models.Model):
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.CASCADE, related_name="comparaciones")
    precio_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_maximo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_promedio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cantidad_fuentes = models.PositiveIntegerField(default=0)
    fuente_mas_barata = models.ForeignKey(
        FuenteWeb,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comparaciones_mas_barata",
    )
    diferencia_porcentual_min_promedio = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    producto_fuente_mas_barato = models.ForeignKey(
        ProductoFuente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comparaciones_como_mas_barato",
    )
    precio_minimo_oportunidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_maximo_oportunidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_promedio_oportunidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    diferencia_pct_min_promedio = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    diferencia_pct_min_max = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cantidad_productos_fuente = models.PositiveIntegerField(default=0)
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comparacion de precio"
        verbose_name_plural = "comparaciones de precio"
        ordering = ["-fecha_calculo"]

    def __str__(self):
        return f"{self.producto_canonico} - {self.fecha_calculo:%Y-%m-%d}"


class SugerenciaMatchingProducto(models.Model):
    NIVEL_ALTO = "alto"
    NIVEL_MEDIO = "medio"
    NIVEL_BAJO = "bajo"
    NIVEL_DESCARTAR = "descartar"
    NIVEL_CHOICES = [
        (NIVEL_ALTO, "Alto"),
        (NIVEL_MEDIO, "Medio"),
        (NIVEL_BAJO, "Bajo"),
        (NIVEL_DESCARTAR, "Descartar"),
    ]
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_ACEPTADA = "aceptada"
    ESTADO_RECHAZADA = "rechazada"
    ESTADO_IGNORADA = "ignorada"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ACEPTADA, "Aceptada"),
        (ESTADO_RECHAZADA, "Rechazada"),
        (ESTADO_IGNORADA, "Ignorada"),
    ]

    producto_a = models.ForeignKey(ProductoFuente, on_delete=models.CASCADE, related_name="sugerencias_matching_a")
    producto_b = models.ForeignKey(ProductoFuente, on_delete=models.CASCADE, related_name="sugerencias_matching_b")
    score = models.PositiveIntegerField(default=0)
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default=NIVEL_DESCARTAR)
    motivos = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    producto_canonico_sugerido = models.ForeignKey(
        ProductoCanonico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sugerencias_matching",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    nota_revision = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "sugerencia de matching de producto"
        verbose_name_plural = "sugerencias de matching de productos"
        ordering = ["-score", "-fecha_creacion"]
        unique_together = ("producto_a", "producto_b")

    def save(self, *args, **kwargs):
        if self.producto_a_id and self.producto_b_id:
            if self.producto_a_id == self.producto_b_id:
                raise ValueError("Un producto no puede compararse consigo mismo.")
            if self.producto_a_id > self.producto_b_id:
                self.producto_a_id, self.producto_b_id = self.producto_b_id, self.producto_a_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.producto_a_id} / #{self.producto_b_id} - {self.score}"


class EvaluacionOportunidadMultifuente(models.Model):
    TIPO_REVENTA = "reventa"
    TIPO_AFILIADO = "afiliado"
    TIPO_OBSERVAR = "observar"
    TIPO_DESCARTAR = "descartar"
    TIPO_TEMPORADA_FUTURA = "temporada_futura"
    TIPO_CHOICES = [
        (TIPO_REVENTA, "Reventa"),
        (TIPO_AFILIADO, "Afiliado"),
        (TIPO_OBSERVAR, "Observar"),
        (TIPO_DESCARTAR, "Descartar"),
        (TIPO_TEMPORADA_FUTURA, "Temporada futura"),
    ]
    RIESGO_BAJO = "bajo"
    RIESGO_MEDIO = "medio"
    RIESGO_ALTO = "alto"
    RIESGO_CHOICES = [
        (RIESGO_BAJO, "Bajo"),
        (RIESGO_MEDIO, "Medio"),
        (RIESGO_ALTO, "Alto"),
    ]

    producto_canonico = models.ForeignKey(
        ProductoCanonico,
        on_delete=models.CASCADE,
        related_name="evaluaciones_multifuente",
    )
    producto_fuente_origen = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2)
    precio_promedio_mercado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_reventa_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    porcentaje_margen = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    indice_oportunidad = models.PositiveIntegerField(default=0)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    riesgo = models.CharField(max_length=20, choices=RIESGO_CHOICES)
    motivo = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evaluacion multifuente"
        verbose_name_plural = "evaluaciones multifuente"
        ordering = ["-indice_oportunidad", "-fecha_creacion"]

    def __str__(self):
        return f"{self.producto_canonico} - {self.tipo}"


class DecisionTecnica(models.Model):
    CATEGORIA_ARQUITECTURA = "arquitectura"
    CATEGORIA_INTEGRACION = "integracion"
    CATEGORIA_MERCADO_LIBRE = "mercado_libre"
    CATEGORIA_SCRAPING = "scraping"
    CATEGORIA_DATOS = "datos"
    CATEGORIA_DESPLIEGUE = "despliegue"
    CATEGORIA_OTRO = "otro"
    CATEGORIA_CHOICES = [
        (CATEGORIA_ARQUITECTURA, "Arquitectura"),
        (CATEGORIA_INTEGRACION, "Integracion"),
        (CATEGORIA_MERCADO_LIBRE, "Mercado Libre"),
        (CATEGORIA_SCRAPING, "Scraping"),
        (CATEGORIA_DATOS, "Datos"),
        (CATEGORIA_DESPLIEGUE, "Despliegue"),
        (CATEGORIA_OTRO, "Otro"),
    ]

    titulo = models.CharField(max_length=200)
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    descripcion = models.TextField()
    decision = models.TextField()
    motivo = models.TextField(blank=True, null=True)
    impacto = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "decision tecnica"
        verbose_name_plural = "decisiones tecnicas"
        ordering = ["-fecha"]

    def __str__(self):
        return self.titulo


class AuditoriaFuenteWeb(models.Model):
    PERMITE_SI = "si"
    PERMITE_NO = "no"
    PERMITE_DUDOSO = "dudoso"
    PERMITE_PENDIENTE = "pendiente"
    PERMITE_CHOICES = [
        (PERMITE_SI, "Si"),
        (PERMITE_NO, "No"),
        (PERMITE_DUDOSO, "Dudoso"),
        (PERMITE_PENDIENTE, "Pendiente"),
    ]

    METODO_API_OFICIAL = "api_oficial"
    METODO_CSV_EXCEL = "csv_excel"
    METODO_CATALOGO_PDF = "catalogo_pdf"
    METODO_SITEMAP = "sitemap"
    METODO_DATOS_ESTRUCTURADOS = "datos_estructurados"
    METODO_CARGA_URL = "carga_url"
    METODO_SCRAPING_CONTROLADO = "scraping_controlado"
    METODO_NO_AUTOMATIZAR = "no_automatizar"
    METODO_PENDIENTE_REVISION = "pendiente_revision"
    METODO_CHOICES = [
        (METODO_API_OFICIAL, "API oficial"),
        (METODO_CSV_EXCEL, "CSV/Excel"),
        (METODO_CATALOGO_PDF, "Catalogo PDF"),
        (METODO_SITEMAP, "Sitemap"),
        (METODO_DATOS_ESTRUCTURADOS, "Datos estructurados"),
        (METODO_CARGA_URL, "Carga URL"),
        (METODO_SCRAPING_CONTROLADO, "Scraping controlado"),
        (METODO_NO_AUTOMATIZAR, "No automatizar"),
        (METODO_PENDIENTE_REVISION, "Pendiente revision"),
    ]

    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.CASCADE, related_name="auditorias")
    url_robots_txt = models.URLField(blank=True, null=True)
    robots_txt_encontrado = models.BooleanField(default=False)
    robots_txt_contenido_resumen = models.TextField(blank=True, null=True)
    sitemap_detectado = models.BooleanField(default=False)
    sitemap_url = models.URLField(blank=True, null=True)
    requiere_login_detectado = models.BooleanField(default=False)
    captcha_detectado = models.BooleanField(default=False)
    bloqueos_detectados = models.BooleanField(default=False)
    status_home = models.PositiveIntegerField(blank=True, null=True)
    status_robots = models.PositiveIntegerField(blank=True, null=True)
    status_sitemap = models.PositiveIntegerField(blank=True, null=True)
    permite_extraccion_segun_revision = models.CharField(
        max_length=20,
        choices=PERMITE_CHOICES,
        default=PERMITE_PENDIENTE,
    )
    metodo_recomendado = models.CharField(
        max_length=40,
        choices=METODO_CHOICES,
        default=METODO_PENDIENTE_REVISION,
    )
    semaforo_sugerido = models.CharField(
        max_length=20,
        choices=PoliticaExtraccionFuente.SEMAFORO_CHOICES,
        default=PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
    )
    resumen_tecnico = models.TextField(blank=True, null=True)
    riesgos_detectados = models.TextField(blank=True, null=True)
    recomendacion = models.TextField(blank=True, null=True)
    revisado_manualmente = models.BooleanField(default=False)
    fecha_auditoria = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "auditoria de fuente web"
        verbose_name_plural = "auditorias de fuentes web"
        ordering = ["-fecha_auditoria"]

    def __str__(self):
        return f"{self.fuente_web} - {self.fecha_auditoria:%Y-%m-%d}"


class RecursoFuenteDetectado(models.Model):
    TIPO_ROBOTS = "robots_txt"
    TIPO_SITEMAP = "sitemap"
    TIPO_CATEGORIA = "categoria"
    TIPO_PRODUCTO = "producto"
    TIPO_CSV = "csv"
    TIPO_EXCEL = "excel"
    TIPO_PDF = "pdf"
    TIPO_FEED = "feed"
    TIPO_PAGINA_INFO = "pagina_info"
    TIPO_OTRO = "otro"
    TIPO_CHOICES = [
        (TIPO_ROBOTS, "Robots.txt"),
        (TIPO_SITEMAP, "Sitemap"),
        (TIPO_CATEGORIA, "Categoria"),
        (TIPO_PRODUCTO, "Producto"),
        (TIPO_CSV, "CSV"),
        (TIPO_EXCEL, "Excel"),
        (TIPO_PDF, "PDF"),
        (TIPO_FEED, "Feed"),
        (TIPO_PAGINA_INFO, "Pagina info"),
        (TIPO_OTRO, "Otro"),
    ]

    auditoria = models.ForeignKey(AuditoriaFuenteWeb, on_delete=models.CASCADE, related_name="recursos")
    tipo_recurso = models.CharField(max_length=30, choices=TIPO_CHOICES)
    url = models.URLField()
    status_code = models.PositiveIntegerField(blank=True, null=True)
    content_type = models.CharField(max_length=150, blank=True, null=True)
    permitido = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True)
    fecha_detectado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "recurso de fuente detectado"
        verbose_name_plural = "recursos de fuentes detectados"
        ordering = ["-fecha_detectado"]

    def __str__(self):
        return f"{self.tipo_recurso} - {self.url}"


class RevisionManualFuente(models.Model):
    TIPO_TERMINOS = "terminos"
    TIPO_ROBOTS = "robots"
    TIPO_PRIVACIDAD = "privacidad"
    TIPO_COMERCIAL = "comercial"
    TIPO_OTRA = "otra"
    TIPO_CHOICES = [
        (TIPO_TERMINOS, "Terminos"),
        (TIPO_ROBOTS, "Robots"),
        (TIPO_PRIVACIDAD, "Privacidad"),
        (TIPO_COMERCIAL, "Comercial"),
        (TIPO_OTRA, "Otra"),
    ]

    RESULTADO_PERMITE = "permite"
    RESULTADO_PROHIBE = "prohibe"
    RESULTADO_DUDOSO = "dudoso"
    RESULTADO_NO_ENCONTRADO = "no_encontrado"
    RESULTADO_PENDIENTE = "pendiente"
    RESULTADO_CHOICES = [
        (RESULTADO_PERMITE, "Permite"),
        (RESULTADO_PROHIBE, "Prohibe"),
        (RESULTADO_DUDOSO, "Dudoso"),
        (RESULTADO_NO_ENCONTRADO, "No encontrado"),
        (RESULTADO_PENDIENTE, "Pendiente"),
    ]

    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.CASCADE, related_name="revisiones_manuales")
    tipo_revision = models.CharField(max_length=30, choices=TIPO_CHOICES)
    url_revisada = models.URLField(blank=True, null=True)
    resultado = models.CharField(max_length=30, choices=RESULTADO_CHOICES, default=RESULTADO_PENDIENTE)
    resumen = models.TextField()
    decision = models.TextField(blank=True, null=True)
    revisado_por = models.CharField(max_length=150, blank=True, null=True)
    fecha_revision = models.DateTimeField(auto_now_add=True)
    aplicar_a_politica = models.BooleanField(default=False)

    class Meta:
        verbose_name = "revision manual de fuente"
        verbose_name_plural = "revisiones manuales de fuentes"
        ordering = ["-fecha_revision"]

    def __str__(self):
        return f"{self.fuente_web} - {self.tipo_revision} - {self.resultado}"


class ConectorFuente(models.Model):
    TIPO_CSV_MANUAL = "csv_manual"
    TIPO_EXCEL_MANUAL = "excel_manual"
    TIPO_CSV_REMOTO = "csv_remoto"
    TIPO_EXCEL_REMOTO = "excel_remoto"
    TIPO_API_OFICIAL = "api_oficial"
    TIPO_CATALOGO_PDF = "catalogo_pdf"
    TIPO_CARGA_URL = "carga_url"
    TIPO_SCRAPING_PERMITIDO = "scraping_permitido"
    TIPO_OTRO = "otro"
    TIPO_CHOICES = [
        (TIPO_CSV_MANUAL, "CSV manual"),
        (TIPO_EXCEL_MANUAL, "Excel manual"),
        (TIPO_CSV_REMOTO, "CSV remoto"),
        (TIPO_EXCEL_REMOTO, "Excel remoto"),
        (TIPO_API_OFICIAL, "API oficial"),
        (TIPO_CATALOGO_PDF, "Catalogo PDF"),
        (TIPO_CARGA_URL, "Carga URL"),
        (TIPO_SCRAPING_PERMITIDO, "Scraping permitido"),
        (TIPO_OTRO, "Otro"),
    ]

    ESTADO_BORRADOR = "borrador"
    ESTADO_ACTIVO = "activo"
    ESTADO_PAUSADO = "pausado"
    ESTADO_ERROR = "error"
    ESTADO_DESHABILITADO = "deshabilitado"
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_ACTIVO, "Activo"),
        (ESTADO_PAUSADO, "Pausado"),
        (ESTADO_ERROR, "Error"),
        (ESTADO_DESHABILITADO, "Deshabilitado"),
    ]

    FORMATO_CSV = "csv"
    FORMATO_XLSX = "xlsx"
    FORMATO_XLS = "xls"
    FORMATO_DESCONOCIDO = "desconocido"
    FORMATO_CHOICES = [
        (FORMATO_CSV, "CSV"),
        (FORMATO_XLSX, "Excel XLSX"),
        (FORMATO_XLS, "Excel XLS"),
        (FORMATO_DESCONOCIDO, "Desconocido"),
    ]

    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.CASCADE, related_name="conectores")
    nombre = models.CharField(max_length=150)
    tipo_conector = models.CharField(max_length=30, choices=TIPO_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    url_recurso = models.URLField(blank=True, null=True)
    formato_recurso = models.CharField(max_length=20, choices=FORMATO_CHOICES, default=FORMATO_DESCONOCIDO)
    requiere_descarga = models.BooleanField(default=False)
    fuente_autorizo_uso = models.BooleanField(default=False)
    descripcion = models.TextField(blank=True, null=True)
    frecuencia_sugerida = models.CharField(max_length=100, blank=True, null=True)
    notas_uso_datos = models.TextField(blank=True, null=True)
    requiere_revision_manual = models.BooleanField(default=True)
    respeta_politica_fuente = models.BooleanField(default=True)
    ultima_ejecucion = models.DateTimeField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "conector de fuente"
        verbose_name_plural = "conectores de fuente"
        ordering = ["fuente_web", "nombre"]

    def __str__(self):
        return f"{self.nombre} - {self.fuente_web}"


class EjecucionConector(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_EJECUTANDO = "ejecutando"
    ESTADO_FINALIZADA = "finalizada"
    ESTADO_FINALIZADA_CON_ERRORES = "finalizada_con_errores"
    ESTADO_ERROR = "error"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_EJECUTANDO, "Ejecutando"),
        (ESTADO_FINALIZADA, "Finalizada"),
        (ESTADO_FINALIZADA_CON_ERRORES, "Finalizada con errores"),
        (ESTADO_ERROR, "Error"),
        (ESTADO_CANCELADA, "Cancelada"),
    ]

    conector = models.ForeignKey(ConectorFuente, on_delete=models.CASCADE, related_name="ejecuciones")
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(blank=True, null=True)
    productos_detectados = models.PositiveIntegerField(default=0)
    productos_creados = models.PositiveIntegerField(default=0)
    productos_actualizados = models.PositiveIntegerField(default=0)
    precios_creados = models.PositiveIntegerField(default=0)
    errores = models.PositiveIntegerField(default=0)
    mensaje = models.TextField(blank=True, null=True)
    log_resumido = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "ejecucion de conector"
        verbose_name_plural = "ejecuciones de conectores"
        ordering = ["-inicio"]

    def __str__(self):
        return f"{self.conector} - {self.estado}"


class DetalleEjecucionConector(models.Model):
    ESTADO_PROCESADO = "procesado"
    ESTADO_OMITIDO = "omitido"
    ESTADO_ERROR = "error"
    ESTADO_CHOICES = [
        (ESTADO_PROCESADO, "Procesado"),
        (ESTADO_OMITIDO, "Omitido"),
        (ESTADO_ERROR, "Error"),
    ]

    ejecucion = models.ForeignKey(EjecucionConector, on_delete=models.CASCADE, related_name="detalles")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    mensaje = models.TextField(blank=True, null=True)
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    datos_originales = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "detalle de ejecucion de conector"
        verbose_name_plural = "detalles de ejecuciones de conectores"
        ordering = ["ejecucion", "fecha_creacion"]

    def __str__(self):
        return f"{self.ejecucion} - {self.estado}"


class ConfiguracionExtractorWeb(models.Model):
    MODO_JSON_LD = "json_ld"
    MODO_CSS_SELECTORS = "css_selectors"
    MODO_MIXTO = "mixto"
    MODO_PREVIEW_MANUAL = "preview_manual"
    MODO_CHOICES = [
        (MODO_JSON_LD, "JSON-LD"),
        (MODO_CSS_SELECTORS, "Selectores CSS"),
        (MODO_MIXTO, "Mixto"),
        (MODO_PREVIEW_MANUAL, "Preview manual"),
    ]

    conector = models.OneToOneField(ConectorFuente, on_delete=models.CASCADE, related_name="configuracion_web")
    pagina_prueba_url = models.URLField(blank=True, null=True)
    url_inicio = models.URLField()
    url_categoria = models.URLField(blank=True, null=True)
    dominio_permitido = models.CharField(max_length=200)
    modo_extraccion = models.CharField(max_length=30, choices=MODO_CHOICES, default=MODO_PREVIEW_MANUAL)
    product_card_selector = models.CharField(max_length=255, blank=True, null=True)
    title_selector = models.CharField(max_length=255, blank=True, null=True)
    price_selector = models.CharField(max_length=255, blank=True, null=True)
    url_selector = models.CharField(max_length=255, blank=True, null=True)
    image_selector = models.CharField(max_length=255, blank=True, null=True)
    description_selector = models.CharField(max_length=255, blank=True, null=True)
    next_page_selector = models.CharField(max_length=255, blank=True, null=True)
    max_paginas = models.PositiveIntegerField(default=1)
    max_productos = models.PositiveIntegerField(default=20)
    delay_segundos = models.DecimalField(max_digits=5, decimal_places=2, default=2)
    timeout_segundos = models.PositiveIntegerField(default=15)
    habilitado = models.BooleanField(default=False)
    solo_preview = models.BooleanField(default=True)
    requiere_js_detectado = models.BooleanField(default=False)
    ultimo_preview_ok = models.BooleanField(default=False)
    ultimo_preview_mensaje = models.TextField(blank=True, null=True)
    ultima_revision_selectores = models.DateTimeField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuracion de extractor web"
        verbose_name_plural = "configuraciones de extractores web"

    def __str__(self):
        return f"Extractor {self.conector}"

    def clean(self):
        errores = {}
        if self.max_paginas and self.max_paginas > 3:
            errores["max_paginas"] = "En esta etapa el extractor no puede superar 3 paginas."
        if self.max_productos and self.max_productos > 100:
            errores["max_productos"] = "En esta etapa el extractor no puede superar 100 productos."
        if self.delay_segundos is not None and self.delay_segundos < Decimal("1.50"):
            errores["delay_segundos"] = "El delay minimo permitido es 1.5 segundos."
        if self.dominio_permitido:
            self.dominio_permitido = normalizar_dominio(self.dominio_permitido)
            for campo in ["pagina_prueba_url", "url_inicio", "url_categoria"]:
                valor = getattr(self, campo)
                if valor and not url_pertenece_a_dominio(valor, self.dominio_permitido):
                    errores[campo] = "La URL debe pertenecer al dominio permitido."
                if valor and valor.strip().lower().startswith(("javascript:", "data:", "mailto:")):
                    errores[campo] = "La URL no puede usar esquemas javascript, data o mailto."
        if self.modo_extraccion == self.MODO_CSS_SELECTORS:
            requeridos = ["product_card_selector", "title_selector", "price_selector"]
            faltantes = [campo for campo in requeridos if not getattr(self, campo)]
            if faltantes:
                errores["modo_extraccion"] = "CSS requiere selector de tarjeta, titulo y precio."
        if errores:
            raise ValidationError(errores)


class ResultadoExtraccionWeb(models.Model):
    ESTADO_DETECTADO = "detectado"
    ESTADO_PROCESADO = "procesado"
    ESTADO_OMITIDO = "omitido"
    ESTADO_ERROR = "error"
    ESTADO_CHOICES = [
        (ESTADO_DETECTADO, "Detectado"),
        (ESTADO_PROCESADO, "Procesado"),
        (ESTADO_OMITIDO, "Omitido"),
        (ESTADO_ERROR, "Error"),
    ]

    ejecucion = models.ForeignKey(EjecucionConector, on_delete=models.CASCADE, related_name="resultados_web")
    lote_captura = models.ForeignKey(
        "LoteCaptura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resultados_extraccion",
    )
    titulo = models.CharField(max_length=255, blank=True, null=True)
    precio_texto = models.CharField(max_length=100, blank=True, null=True)
    precio_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_lista_texto = models.CharField(max_length=100, blank=True, null=True)
    precio_lista_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_transferencia_texto = models.CharField(max_length=150, blank=True, null=True)
    precio_transferencia_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_tarjeta_texto = models.CharField(max_length=150, blank=True, null=True)
    precio_tarjeta_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cuotas_texto = models.CharField(max_length=200, blank=True, null=True)
    precio_oportunidad_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tipo_precio_oportunidad = models.CharField(
        max_length=20,
        choices=PrecioFuente.TIPO_PRECIO_CHOICES,
        default=PrecioFuente.TIPO_PRECIO_DESCONOCIDO,
    )
    texto_precios_detectado = models.TextField(blank=True, null=True)
    texto_demanda_detectado = models.TextField(blank=True, null=True)
    score_demanda_preview = models.PositiveIntegerField(default=0)
    nivel_demanda_preview = models.CharField(
        max_length=20,
        choices=ProductoFuente.DEMANDA_CHOICES,
        default=ProductoFuente.DEMANDA_DESCONOCIDA,
    )
    url_producto = models.URLField(blank=True, null=True)
    imagen_url = models.URLField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    fuente_url = models.URLField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_DETECTADO)
    seleccionado = models.BooleanField(default=False)
    procesable = models.BooleanField(default=True)
    motivo_no_procesable = models.TextField(blank=True, null=True)
    score_preview = models.PositiveIntegerField(default=0)
    motivo_score = models.TextField(blank=True, null=True)
    duplicado_probable = models.BooleanField(default=False)
    mensaje = models.TextField(blank=True, null=True)
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    raw_data = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_procesamiento = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "resultado de extraccion web"
        verbose_name_plural = "resultados de extraccion web"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.titulo or f"Resultado #{self.pk}"


class SesionLaboratorioMapeo(models.Model):
    ESTADO_ANALIZADA = "analizada"
    ESTADO_GUARDADA = "guardada"
    ESTADO_PROCESADA = "procesada"
    ESTADO_ERROR = "error"
    ESTADO_CHOICES = [
        (ESTADO_ANALIZADA, "Analizada"),
        (ESTADO_GUARDADA, "Guardada"),
        (ESTADO_PROCESADA, "Procesada"),
        (ESTADO_ERROR, "Error"),
    ]

    url = models.URLField()
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.SET_NULL, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_ANALIZADA)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    requiere_js_probable = models.BooleanField(default=False)
    tiene_json_ld = models.BooleanField(default=False)
    bloqueos_detectados = models.TextField(blank=True, null=True)
    selectores_sugeridos = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sesion de laboratorio de mapeo"
        verbose_name_plural = "sesiones de laboratorio de mapeo"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Laboratorio {self.url}"


class ResultadoLaboratorioMapeo(models.Model):
    sesion = models.ForeignKey(SesionLaboratorioMapeo, on_delete=models.CASCADE, related_name="resultados")
    lote_captura = models.ForeignKey(
        "LoteCaptura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resultados_laboratorio",
    )
    titulo = models.CharField(max_length=255, blank=True, null=True)
    precio_texto = models.CharField(max_length=100, blank=True, null=True)
    precio_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_lista_texto = models.CharField(max_length=100, blank=True, null=True)
    precio_lista_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_transferencia_texto = models.CharField(max_length=150, blank=True, null=True)
    precio_transferencia_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_tarjeta_texto = models.CharField(max_length=150, blank=True, null=True)
    precio_tarjeta_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cuotas_texto = models.CharField(max_length=200, blank=True, null=True)
    precio_oportunidad_decimal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tipo_precio_oportunidad = models.CharField(
        max_length=20,
        choices=PrecioFuente.TIPO_PRECIO_CHOICES,
        default=PrecioFuente.TIPO_PRECIO_DESCONOCIDO,
    )
    texto_precios_detectado = models.TextField(blank=True, null=True)
    texto_demanda_detectado = models.TextField(blank=True, null=True)
    score_demanda_preview = models.PositiveIntegerField(default=0)
    nivel_demanda_preview = models.CharField(
        max_length=20,
        choices=ProductoFuente.DEMANDA_CHOICES,
        default=ProductoFuente.DEMANDA_DESCONOCIDA,
    )
    url_producto = models.URLField(blank=True, null=True)
    imagen_url = models.URLField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    score = models.PositiveIntegerField(default=0)
    seleccionado = models.BooleanField(default=False)
    procesado = models.BooleanField(default=False)
    mensaje = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "resultado de laboratorio de mapeo"
        verbose_name_plural = "resultados de laboratorio de mapeo"
        ordering = ["-score", "id"]

    def __str__(self):
        return self.titulo or f"Resultado laboratorio #{self.pk}"


class ImportacionProductos(models.Model):
    TIPO_CSV = "csv"
    TIPO_XLSX = "xlsx"
    TIPO_XLS = "xls"
    TIPO_DESCONOCIDO = "desconocido"
    TIPO_ARCHIVO_CHOICES = [
        (TIPO_CSV, "CSV"),
        (TIPO_XLSX, "Excel XLSX"),
        (TIPO_XLS, "Excel XLS"),
        (TIPO_DESCONOCIDO, "Desconocido"),
    ]

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_PROCESANDO = "procesando"
    ESTADO_PROCESADA = "procesada"
    ESTADO_PROCESADA_CON_ERRORES = "procesada_con_errores"
    ESTADO_ERROR = "error"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_PROCESANDO, "Procesando"),
        (ESTADO_PROCESADA, "Procesada"),
        (ESTADO_PROCESADA_CON_ERRORES, "Procesada con errores"),
        (ESTADO_ERROR, "Error"),
    ]

    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.PROTECT, related_name="importaciones")
    conector = models.ForeignKey(
        ConectorFuente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="importaciones",
    )
    archivo = models.FileField(upload_to="importaciones/productos/")
    tipo_archivo = models.CharField(max_length=20, choices=TIPO_ARCHIVO_CHOICES, default=TIPO_DESCONOCIDO)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    total_filas = models.PositiveIntegerField(default=0)
    filas_procesadas = models.PositiveIntegerField(default=0)
    productos_creados = models.PositiveIntegerField(default=0)
    productos_actualizados = models.PositiveIntegerField(default=0)
    precios_creados = models.PositiveIntegerField(default=0)
    errores = models.PositiveIntegerField(default=0)
    mensaje_error = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_procesamiento = models.DateTimeField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "importacion de productos"
        verbose_name_plural = "importaciones de productos"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Importacion #{self.pk} - {self.fuente_web}"


class DetalleImportacionProducto(models.Model):
    ESTADO_PROCESADA = "procesada"
    ESTADO_OMITIDA = "omitida"
    ESTADO_ERROR = "error"
    ESTADO_CHOICES = [
        (ESTADO_PROCESADA, "Procesada"),
        (ESTADO_OMITIDA, "Omitida"),
        (ESTADO_ERROR, "Error"),
    ]

    importacion = models.ForeignKey(ImportacionProductos, on_delete=models.CASCADE, related_name="detalles")
    numero_fila = models.PositiveIntegerField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    mensaje = models.TextField(blank=True, null=True)
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    precio_fuente = models.ForeignKey(PrecioFuente, on_delete=models.SET_NULL, null=True, blank=True)
    datos_originales = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "detalle de importacion de producto"
        verbose_name_plural = "detalles de importacion de productos"
        ordering = ["importacion", "numero_fila"]

    def __str__(self):
        return f"Fila {self.numero_fila} - {self.estado}"


class PrecioProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="precios")
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    costo_envio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    moneda = models.CharField(max_length=10, default="ARS")
    fecha_relevamiento = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "precio de producto"
        verbose_name_plural = "precios de producto"
        ordering = ["-fecha_relevamiento"]

    def __str__(self):
        return f"{self.producto} - {self.moneda} {self.precio}"


class Oportunidad(models.Model):
    TIPO_AFILIADO = "afiliado"
    TIPO_REVENTA = "reventa"
    TIPO_DESCARTAR = "descartar"
    TIPO_CHOICES = [
        (TIPO_AFILIADO, "Afiliado"),
        (TIPO_REVENTA, "Reventa"),
        (TIPO_DESCARTAR, "Descartar"),
    ]

    RIESGO_BAJO = "bajo"
    RIESGO_MEDIO = "medio"
    RIESGO_ALTO = "alto"
    RIESGO_CHOICES = [
        (RIESGO_BAJO, "Bajo"),
        (RIESGO_MEDIO, "Medio"),
        (RIESGO_ALTO, "Alto"),
    ]

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_REVISADO = "revisado"
    ESTADO_PUBLICADO = "publicado"
    ESTADO_COMPRADO = "comprado"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_REVISADO, "Revisado"),
        (ESTADO_PUBLICADO, "Publicado"),
        (ESTADO_COMPRADO, "Comprado"),
        (ESTADO_DESCARTADO, "Descartado"),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="oportunidades")
    precio_referencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_actual = models.DecimalField(max_digits=12, decimal_places=2)
    precio_reventa_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    porcentaje_margen = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    puntaje = models.PositiveIntegerField(default=0)
    riesgo = models.CharField(max_length=20, choices=RIESGO_CHOICES)
    motivo = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-puntaje", "-fecha_creacion"]

    def __str__(self):
        return f"{self.producto} ({self.tipo})"


class ContenidoSugerido(models.Model):
    oportunidad = models.ForeignKey(Oportunidad, on_delete=models.CASCADE, related_name="contenidos")
    gancho = models.CharField(max_length=255)
    guion_corto = models.TextField()
    descripcion = models.TextField()
    hashtags = models.CharField(max_length=255)
    generado_con_ia = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "contenido sugerido"
        verbose_name_plural = "contenidos sugeridos"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.gancho


class Publicacion(models.Model):
    RED_TIKTOK = "tiktok"
    RED_INSTAGRAM = "instagram"
    RED_WHATSAPP = "whatsapp"
    RED_TELEGRAM = "telegram"
    RED_OTRA = "otra"
    RED_CHOICES = [
        (RED_TIKTOK, "TikTok"),
        (RED_INSTAGRAM, "Instagram"),
        (RED_WHATSAPP, "WhatsApp"),
        (RED_TELEGRAM, "Telegram"),
        (RED_OTRA, "Otra"),
    ]

    oportunidad = models.ForeignKey(Oportunidad, on_delete=models.CASCADE, related_name="publicaciones")
    red_social = models.CharField(max_length=20, choices=RED_CHOICES)
    fecha_publicacion = models.DateTimeField()
    url_publicacion = models.URLField(blank=True, null=True)
    vistas = models.PositiveIntegerField(default=0)
    clics = models.PositiveIntegerField(default=0)
    ventas_reportadas = models.PositiveIntegerField(default=0)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "publicacion"
        verbose_name_plural = "publicaciones"
        ordering = ["-fecha_publicacion"]

    def __str__(self):
        return f"{self.get_red_social_display()} - {self.oportunidad}"


class LoteCaptura(models.Model):
    ORIGEN_LABORATORIO = "laboratorio"
    ORIGEN_EXTRACTOR_WEB = "extractor_web"
    ORIGEN_IMPORTACION = "importacion_csv_excel"
    ORIGEN_CARGA_URL = "carga_url"
    ORIGEN_MANUAL = "manual"
    ORIGEN_API = "api"
    ORIGEN_OTRO = "otro"
    ORIGEN_CHOICES = [
        (ORIGEN_LABORATORIO, "Laboratorio"),
        (ORIGEN_EXTRACTOR_WEB, "Extractor web"),
        (ORIGEN_IMPORTACION, "Importacion CSV/Excel"),
        (ORIGEN_CARGA_URL, "Carga URL"),
        (ORIGEN_MANUAL, "Manual"),
        (ORIGEN_API, "API"),
        (ORIGEN_OTRO, "Otro"),
    ]
    TIPO_PRUEBA = "prueba"
    TIPO_PILOTO = "piloto"
    TIPO_REAL = "real"
    TIPO_HISTORICA = "historica"
    TIPO_DESCARTE = "descarte"
    TIPO_CARGA_CHOICES = [
        (TIPO_PRUEBA, "Prueba"),
        (TIPO_PILOTO, "Piloto"),
        (TIPO_REAL, "Real"),
        (TIPO_HISTORICA, "Historica"),
        (TIPO_DESCARTE, "Descarte"),
    ]
    ESTADO_CREADO = "creado"
    ESTADO_EJECUTANDO = "ejecutando"
    ESTADO_PROCESADO = "procesado"
    ESTADO_PROCESADO_CON_ERRORES = "procesado_con_errores"
    ESTADO_VALIDADO = "validado"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_ERROR = "error"
    ESTADO_CHOICES = [
        (ESTADO_CREADO, "Creado"),
        (ESTADO_EJECUTANDO, "Ejecutando"),
        (ESTADO_PROCESADO, "Procesado"),
        (ESTADO_PROCESADO_CON_ERRORES, "Procesado con errores"),
        (ESTADO_VALIDADO, "Validado"),
        (ESTADO_DESCARTADO, "Descartado"),
        (ESTADO_ERROR, "Error"),
    ]

    nombre = models.CharField(max_length=200)
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.PROTECT, null=True, blank=True, related_name="lotes_captura")
    conector = models.ForeignKey(ConectorFuente, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes_captura")
    extractor = models.ForeignKey(ConfiguracionExtractorWeb, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes_captura")
    importacion = models.ForeignKey(ImportacionProductos, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes_captura")
    sesion_laboratorio = models.ForeignKey(SesionLaboratorioMapeo, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes_captura")
    ejecucion_conector = models.ForeignKey(EjecucionConector, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes_captura")
    origen = models.CharField(max_length=30, choices=ORIGEN_CHOICES)
    tipo_carga = models.CharField(max_length=20, choices=TIPO_CARGA_CHOICES, default=TIPO_PILOTO)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default=ESTADO_CREADO)
    url_origen = models.URLField(blank=True, null=True)
    url_categoria = models.URLField(blank=True, null=True)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    fecha_relevamiento = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    usuario_texto = models.CharField(max_length=150, blank=True, null=True)
    productos_detectados = models.PositiveIntegerField(default=0)
    productos_seleccionados = models.PositiveIntegerField(default=0)
    productos_procesados = models.PositiveIntegerField(default=0)
    productos_creados = models.PositiveIntegerField(default=0)
    productos_actualizados = models.PositiveIntegerField(default=0)
    precios_creados = models.PositiveIntegerField(default=0)
    senales_demanda_creadas = models.PositiveIntegerField(default=0)
    errores = models.PositiveIntegerField(default=0)
    requiere_revision = models.BooleanField(default=False)
    apto_dataset = models.BooleanField(default=True)
    excluir_ml = models.BooleanField(default=False)
    motivo_exclusion = models.TextField(blank=True, null=True)
    parametros = models.TextField(blank=True, null=True)
    resumen = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "lote de captura"
        verbose_name_plural = "lotes de captura"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return self.nombre


class DetalleLoteCaptura(models.Model):
    ESTADO_DETECTADO = "detectado"
    ESTADO_SELECCIONADO = "seleccionado"
    ESTADO_PROCESADO = "procesado"
    ESTADO_OMITIDO = "omitido"
    ESTADO_ERROR = "error"
    ESTADO_CHOICES = [
        (ESTADO_DETECTADO, "Detectado"),
        (ESTADO_SELECCIONADO, "Seleccionado"),
        (ESTADO_PROCESADO, "Procesado"),
        (ESTADO_OMITIDO, "Omitido"),
        (ESTADO_ERROR, "Error"),
    ]

    lote = models.ForeignKey(LoteCaptura, on_delete=models.CASCADE, related_name="detalles")
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    precio_fuente = models.ForeignKey(PrecioFuente, on_delete=models.SET_NULL, null=True, blank=True)
    resultado_extraccion = models.ForeignKey(ResultadoExtraccionWeb, on_delete=models.SET_NULL, null=True, blank=True)
    resultado_laboratorio = models.ForeignKey(ResultadoLaboratorioMapeo, on_delete=models.SET_NULL, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    mensaje = models.TextField(blank=True, null=True)
    datos_originales = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "detalle de lote de captura"
        verbose_name_plural = "detalles de lotes de captura"
        ordering = ["lote", "fecha", "id"]

    def __str__(self):
        return f"{self.lote} - {self.estado}"


class ComercioLocal(models.Model):
    MODALIDAD_PRESENCIAL = "presencial"
    MODALIDAD_ONLINE = "online"
    MODALIDAD_AMBAS = "ambas"
    MODALIDAD_CHOICES = [
        (MODALIDAD_PRESENCIAL, "Presencial"),
        (MODALIDAD_ONLINE, "Online"),
        (MODALIDAD_AMBAS, "Ambas"),
    ]
    VERIFICACION_PENDIENTE = "pendiente"
    VERIFICACION_VERIFICADO = "verificado"
    VERIFICACION_DESCARTADO = "descartado"
    VERIFICACION_CHOICES = [
        (VERIFICACION_PENDIENTE, "Pendiente"),
        (VERIFICACION_VERIFICADO, "Verificado"),
        (VERIFICACION_DESCARTADO, "Descartado"),
    ]

    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.SET_NULL, null=True, blank=True, related_name="comercios_locales")
    nombre = models.CharField(max_length=180)
    tipo_fuente = models.CharField(max_length=30, choices=FuenteWeb.TIPO_CHOICES, default=FuenteWeb.TIPO_CAPTURA_MANUAL)
    sucursal = models.CharField(max_length=150, blank=True, null=True)
    provincia = models.CharField(max_length=80, default="Salta")
    ciudad = models.CharField(max_length=100, default="Salta Capital")
    zona = models.CharField(max_length=150, default="Salta Capital")
    direccion_referencia = models.CharField(max_length=255, blank=True, null=True)
    modalidad = models.CharField(max_length=20, choices=MODALIDAD_CHOICES, default=MODALIDAD_PRESENCIAL)
    entrega_domicilio = models.BooleanField(default=False)
    retiro = models.BooleanField(default=True)
    requiere_visita = models.BooleanField(default=True)
    contacto_publico = models.CharField(max_length=180, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    estado_verificacion = models.CharField(max_length=20, choices=VERIFICACION_CHOICES, default=VERIFICACION_PENDIENTE)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "comercio local"
        verbose_name_plural = "comercios locales"
        ordering = ["ciudad", "zona", "nombre"]
        indexes = [models.Index(fields=["ciudad", "zona", "nombre"])]

    def __str__(self):
        return f"{self.nombre} - {self.zona}"


class LoteCapturaLocal(models.Model):
    ESTADO_BORRADOR = "borrador"
    ESTADO_PENDIENTE_REVISION = "pendiente_revision"
    ESTADO_VALIDADO = "validado"
    ESTADO_PUBLICADO = "publicado"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_CHOICES = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_PENDIENTE_REVISION, "Pendiente de revision"),
        (ESTADO_VALIDADO, "Validado"),
        (ESTADO_PUBLICADO, "Publicado"),
        (ESTADO_DESCARTADO, "Descartado"),
    ]
    METODO_CARGA_MANUAL = "carga_manual"
    METODO_TABLA_MARKDOWN = "tabla_markdown"
    METODO_CSV = "csv"
    METODO_FOTO_GONDOLA = "foto_gondola"
    METODO_TICKET = "ticket"
    METODO_FOLLETO = "folleto"
    METODO_PDF = "pdf"
    METODO_CATALOGO = "catalogo"
    METODO_MENSAJE_LISTA = "mensaje_lista_precios"
    METODO_OTRO = "otro"
    METODO_CHOICES = [
        (METODO_CARGA_MANUAL, "Carga manual"),
        (METODO_TABLA_MARKDOWN, "Tabla Markdown"),
        (METODO_CSV, "CSV"),
        (METODO_FOTO_GONDOLA, "Foto de gondola"),
        (METODO_TICKET, "Ticket"),
        (METODO_FOLLETO, "Folleto"),
        (METODO_PDF, "PDF"),
        (METODO_CATALOGO, "Catalogo"),
        (METODO_MENSAJE_LISTA, "Mensaje o lista de precios"),
        (METODO_OTRO, "Otro"),
    ]

    nombre = models.CharField(max_length=200)
    fecha_observacion = models.DateTimeField(default=timezone.now)
    fecha_carga = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    zona = models.CharField(max_length=150, default="Salta Capital")
    comercio = models.ForeignKey(ComercioLocal, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes")
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes_locales")
    metodo_captura = models.CharField(max_length=30, choices=METODO_CHOICES, default=METODO_CARGA_MANUAL)
    texto_original = models.TextField(blank=True, null=True)
    cantidad_filas = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    observaciones = models.TextField(blank=True, null=True)
    hash_importacion = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    posible_duplicado = models.BooleanField(default=False)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "lote de captura local"
        verbose_name_plural = "lotes de captura local"
        ordering = ["-fecha_observacion", "-fecha_carga"]
        indexes = [models.Index(fields=["estado", "zona", "fecha_observacion"])]

    def __str__(self):
        return f"{self.nombre} ({self.zona})"


class UmbralPrecioLocal(models.Model):
    UNIDAD_UNIDAD = "unidad"
    UNIDAD_LITRO = "litro"
    UNIDAD_KG = "kg"
    UNIDAD_METRO = "metro"
    UNIDAD_100ML = "100ml"
    UNIDAD_100G = "100g"
    UNIDAD_CHOICES = [
        (UNIDAD_UNIDAD, "$/unidad"),
        (UNIDAD_LITRO, "$/litro"),
        (UNIDAD_KG, "$/kg"),
        (UNIDAD_METRO, "$/metro"),
        (UNIDAD_100ML, "$/100 ml"),
        (UNIDAD_100G, "$/100 g"),
    ]
    USO_CONSUMO_PROPIO = "consumo_propio"
    USO_CONSUMO_FAMILIAR = "consumo_familiar"
    USO_COMPRA_ECONOMICA = "compra_economica"
    USO_STOCK_FAMILIAR = "stock_familiar"
    USO_REVENTA = "posible_reventa"
    USO_ANIMAL_INFORMADA = "alimentacion_animal_informada"
    USO_DONACION = "donacion"
    USO_OTRA = "otra"
    USO_CHOICES = [
        (USO_CONSUMO_PROPIO, "Consumo propio"),
        (USO_CONSUMO_FAMILIAR, "Consumo familiar"),
        (USO_COMPRA_ECONOMICA, "Compra economica"),
        (USO_STOCK_FAMILIAR, "Stock familiar"),
        (USO_REVENTA, "Posible reventa"),
        (USO_ANIMAL_INFORMADA, "Alimentacion animal informada"),
        (USO_DONACION, "Donacion"),
        (USO_OTRA, "Otra"),
    ]

    nombre = models.CharField(max_length=180)
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True, related_name="umbrales_locales")
    categoria = models.ForeignKey(CategoriaInteres, on_delete=models.SET_NULL, null=True, blank=True, related_name="umbrales_locales")
    grupo_comparable = models.CharField(max_length=150, blank=True, null=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    marca_importa = models.BooleanField(default=False)
    segunda_marca_aceptada = models.BooleanField(default=True)
    zona = models.CharField(max_length=150, blank=True, null=True)
    tipo_fuente = models.CharField(max_length=30, choices=FuenteWeb.TIPO_CHOICES, blank=True, null=True)
    uso = models.CharField(max_length=40, choices=USO_CHOICES, blank=True, null=True)
    unidad_normalizada = models.CharField(max_length=20, choices=UNIDAD_CHOICES)
    precio_maximo_bueno = models.DecimalField(max_digits=12, decimal_places=2)
    precio_maximo_fuerte = models.DecimalField(max_digits=12, decimal_places=2)
    moneda = models.CharField(max_length=10, default="ARS")
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    origen_justificacion = models.TextField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "umbral de precio local"
        verbose_name_plural = "umbrales de precio local"
        ordering = ["-activo", "nombre"]
        indexes = [models.Index(fields=["activo", "unidad_normalizada", "zona"])]

    def __str__(self):
        return f"{self.nombre} - {self.get_unidad_normalizada_display()}"


class ObservacionPrecioLocal(models.Model):
    TIPO_UNIDAD = "unidad"
    TIPO_PAQUETE = "paquete"
    TIPO_PACK = "pack"
    TIPO_FARDO = "fardo"
    TIPO_BULTO = "bulto"
    TIPO_CAJA = "caja"
    TIPO_BOLSA = "bolsa"
    TIPO_BOTELLA = "botella"
    TIPO_LATA = "lata"
    TIPO_ROLLO = "rollo"
    TIPO_KILOGRAMO = "kilogramo"
    TIPO_PROMOCION = "promocion"
    TIPO_OTRA = "otra"
    TIPO_PRESENTACION_CHOICES = [
        (TIPO_UNIDAD, "Unidad"),
        (TIPO_PAQUETE, "Paquete"),
        (TIPO_PACK, "Pack"),
        (TIPO_FARDO, "Fardo"),
        (TIPO_BULTO, "Bulto"),
        (TIPO_CAJA, "Caja"),
        (TIPO_BOLSA, "Bolsa"),
        (TIPO_BOTELLA, "Botella"),
        (TIPO_LATA, "Lata"),
        (TIPO_ROLLO, "Rollo"),
        (TIPO_KILOGRAMO, "Kilogramo"),
        (TIPO_PROMOCION, "Promocion"),
        (TIPO_OTRA, "Otra"),
    ]
    STOCK_DESCONOCIDO = "desconocido"
    STOCK_BAJO = "bajo"
    STOCK_MEDIO = "medio"
    STOCK_ALTO = "alto"
    STOCK_AGOTADO = "agotado"
    STOCK_CHOICES = [
        (STOCK_DESCONOCIDO, "Desconocido"),
        (STOCK_BAJO, "Bajo"),
        (STOCK_MEDIO, "Medio"),
        (STOCK_ALTO, "Alto"),
        (STOCK_AGOTADO, "Agotado"),
    ]
    VIGENCIA_SIN_CONFIRMAR = "sin_confirmar"
    VIGENCIA_VIGENTE = "vigente"
    VIGENCIA_POSIBLEMENTE = "posiblemente_vigente"
    VIGENCIA_VENCIDA = "vencida"
    VIGENCIA_AGOTADA = "agotada"
    VIGENCIA_DESCARTADA = "descartada"
    VIGENCIA_CHOICES = [
        (VIGENCIA_SIN_CONFIRMAR, "Sin confirmar"),
        (VIGENCIA_VIGENTE, "Vigente"),
        (VIGENCIA_POSIBLEMENTE, "Posiblemente vigente"),
        (VIGENCIA_VENCIDA, "Vencida"),
        (VIGENCIA_AGOTADA, "Agotada"),
        (VIGENCIA_DESCARTADA, "Descartada"),
    ]
    CLASIFICACION_ALERTA_FUERTE = "alerta_fuerte"
    CLASIFICACION_BUENA = "buena_oportunidad"
    CLASIFICACION_VIGILAR = "vigilar"
    CLASIFICACION_REVISAR = "revisar"
    CLASIFICACION_DESCARTAR = "descartar"
    CLASIFICACION_CHOICES = [
        (CLASIFICACION_ALERTA_FUERTE, "Alerta fuerte"),
        (CLASIFICACION_BUENA, "Buena oportunidad"),
        (CLASIFICACION_VIGILAR, "Vigilar"),
        (CLASIFICACION_REVISAR, "Revisar"),
        (CLASIFICACION_DESCARTAR, "Descartar"),
    ]
    METODO_DESCUENTO_RELATIVO = "descuento_relativo"
    METODO_PRECIO_UMBRAL = "precio_umbral"
    METODO_MEJOR_HISTORICO = "mejor_precio_historico"
    METODO_EVALUACION_MANUAL = "evaluacion_manual"

    lote = models.ForeignKey(LoteCapturaLocal, on_delete=models.SET_NULL, null=True, blank=True, related_name="observaciones_precio")
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True, related_name="observaciones_locales")
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True, related_name="observaciones_locales")
    categoria = models.ForeignKey(CategoriaInteres, on_delete=models.SET_NULL, null=True, blank=True, related_name="observaciones_locales")
    nombre_original = models.CharField(max_length=255)
    marca = models.CharField(max_length=100, blank=True, null=True)
    segunda_marca = models.BooleanField(default=False)
    comercio = models.ForeignKey(ComercioLocal, on_delete=models.SET_NULL, null=True, blank=True, related_name="observaciones_precio")
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.SET_NULL, null=True, blank=True, related_name="observaciones_locales")
    sucursal = models.CharField(max_length=150, blank=True, null=True)
    zona = models.CharField(max_length=150, default="Salta Capital")
    fecha_observacion = models.DateTimeField(default=timezone.now)
    precio_total_encontrado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    moneda = models.CharField(max_length=10, default="ARS")
    tipo_presentacion = models.CharField(max_length=30, choices=TIPO_PRESENTACION_CHOICES, default=TIPO_UNIDAD)
    cantidad_envases = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    contenido_por_envase = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    unidad_medida = models.CharField(max_length=20, default="unidad")
    unidades_totales = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    contenido_total_normalizado = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    precio_por_unidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_por_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_por_litro = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_por_metro = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_traslado_envio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_final_puesto_salta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_estimado = models.CharField(max_length=20, choices=STOCK_CHOICES, default=STOCK_DESCONOCIDO)
    limite_por_cliente = models.CharField(max_length=100, blank=True, null=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    vencimiento_proximo = models.BooleanField(default=False)
    requiere_revisar_vencimiento = models.BooleanField(default=False)
    requiere_visita = models.BooleanField(default=True)
    captura_manual = models.BooleanField(default=True)
    estado_vigencia = models.CharField(max_length=30, choices=VIGENCIA_CHOICES, default=VIGENCIA_SIN_CONFIRMAR)
    fecha_estimada_fin = models.DateTimeField(null=True, blank=True)
    ultima_verificacion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    sirve_para = models.TextField(blank=True, null=True)
    marca_importa = models.BooleanField(default=False)
    segunda_marca_aceptada = models.BooleanField(default=True)
    calidad_minima_observacion = models.TextField(blank=True, null=True)
    cantidad_deseada = models.CharField(max_length=100, blank=True, null=True)
    cantidad_minima_compra = models.CharField(max_length=100, blank=True, null=True)
    cantidad_maxima_permitida = models.CharField(max_length=100, blank=True, null=True)
    riesgo_vencimiento = models.CharField(max_length=150, blank=True, null=True)
    dificultad_traslado = models.CharField(max_length=150, blank=True, null=True)
    clasificacion_automatica = models.CharField(max_length=30, choices=CLASIFICACION_CHOICES, default=CLASIFICACION_REVISAR)
    clasificacion_manual = models.CharField(max_length=30, choices=CLASIFICACION_CHOICES, blank=True, null=True)
    clasificacion_final = models.CharField(max_length=30, choices=CLASIFICACION_CHOICES, default=CLASIFICACION_REVISAR)
    metodo_evaluacion = models.CharField(max_length=120, blank=True, null=True)
    motivo_clasificacion = models.TextField(blank=True, null=True)
    umbral_aplicado = models.ForeignKey(UmbralPrecioLocal, on_delete=models.SET_NULL, null=True, blank=True, related_name="observaciones_precio")
    unidad_umbral_aplicada = models.CharField(max_length=20, blank=True, null=True)
    precio_normalizado_usado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    diferencia_umbral = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    porcentaje_vs_umbral = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    estado_publicacion = models.CharField(max_length=30, choices=LoteCapturaLocal.ESTADO_CHOICES, default=LoteCapturaLocal.ESTADO_BORRADOR)
    raw_data = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "observacion de precio local"
        verbose_name_plural = "observaciones de precio local"
        ordering = ["clasificacion_final", "-fecha_observacion", "nombre_original"]
        indexes = [
            models.Index(fields=["estado_publicacion", "clasificacion_final"]),
            models.Index(fields=["zona", "fecha_observacion"]),
            models.Index(fields=["nombre_original", "comercio"]),
        ]

    def __str__(self):
        return f"{self.nombre_original} - {self.zona}"


class ObjetivoVigilanciaLocal(models.Model):
    ESTADO_ACTIVO = "activo"
    ESTADO_CON_PRECIO = "con_precio"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_CHOICES = [
        (ESTADO_ACTIVO, "Activo"),
        (ESTADO_CON_PRECIO, "Con precio observado"),
        (ESTADO_DESCARTADO, "Descartado"),
    ]

    lote = models.ForeignKey(LoteCapturaLocal, on_delete=models.SET_NULL, null=True, blank=True, related_name="objetivos")
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True, related_name="objetivos_locales")
    categoria = models.ForeignKey(CategoriaInteres, on_delete=models.SET_NULL, null=True, blank=True, related_name="objetivos_locales")
    nombre_objetivo = models.CharField(max_length=255)
    comercio = models.ForeignKey(ComercioLocal, on_delete=models.SET_NULL, null=True, blank=True, related_name="objetivos")
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.SET_NULL, null=True, blank=True, related_name="objetivos_locales")
    zona = models.CharField(max_length=150, default="Salta Capital")
    unidad_deseada = models.CharField(max_length=80, blank=True, null=True)
    sirve_para = models.TextField(blank=True, null=True)
    motivo = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_ACTIVO)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "objetivo de vigilancia local"
        verbose_name_plural = "objetivos de vigilancia local"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.nombre_objetivo


class EvidenciaLocal(models.Model):
    TIPO_FOTO_GONDOLA = "foto_gondola"
    TIPO_FOTO_CARTEL = "foto_cartel"
    TIPO_FOTO_TICKET = "foto_ticket"
    TIPO_FOLLETO = "folleto"
    TIPO_PDF = "pdf"
    TIPO_CATALOGO = "catalogo"
    TIPO_URL = "url"
    TIPO_TEXTO = "texto_manual"
    TIPO_NINGUNA = "ninguna"
    TIPO_CHOICES = [
        (TIPO_FOTO_GONDOLA, "Foto de gondola"),
        (TIPO_FOTO_CARTEL, "Foto de cartel"),
        (TIPO_FOTO_TICKET, "Foto de ticket"),
        (TIPO_FOLLETO, "Folleto"),
        (TIPO_PDF, "PDF"),
        (TIPO_CATALOGO, "Catalogo"),
        (TIPO_URL, "URL"),
        (TIPO_TEXTO, "Texto manual"),
        (TIPO_NINGUNA, "Ninguna"),
    ]
    NIVEL_VERIFICADA = "verificada"
    NIVEL_PARCIAL = "evidencia_parcial"
    NIVEL_MANUAL = "informada_manualmente"
    NIVEL_PENDIENTE = "pendiente"
    NIVEL_RECHAZADA = "rechazada"
    NIVEL_CHOICES = [
        (NIVEL_VERIFICADA, "Verificada"),
        (NIVEL_PARCIAL, "Evidencia parcial"),
        (NIVEL_MANUAL, "Informada manualmente"),
        (NIVEL_PENDIENTE, "Pendiente"),
        (NIVEL_RECHAZADA, "Rechazada"),
    ]

    observacion = models.ForeignKey(ObservacionPrecioLocal, on_delete=models.CASCADE, related_name="evidencias")
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default=TIPO_TEXTO)
    archivo = models.FileField(upload_to="evidencias_locales/%Y/%m/", blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    fecha = models.DateTimeField(default=timezone.now)
    observacion_texto = models.TextField(blank=True, null=True)
    nivel_verificacion = models.CharField(max_length=30, choices=NIVEL_CHOICES, default=NIVEL_PENDIENTE)
    privada = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evidencia local"
        verbose_name_plural = "evidencias locales"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.observacion}"


class CorreccionClasificacionLocal(models.Model):
    observacion = models.ForeignKey(ObservacionPrecioLocal, on_delete=models.CASCADE, related_name="correcciones")
    clasificacion_anterior = models.CharField(max_length=30, choices=ObservacionPrecioLocal.CLASIFICACION_CHOICES)
    clasificacion_nueva = models.CharField(max_length=30, choices=ObservacionPrecioLocal.CLASIFICACION_CHOICES)
    motivo = models.TextField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "correccion de clasificacion local"
        verbose_name_plural = "correcciones de clasificacion local"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.observacion} {self.clasificacion_anterior} -> {self.clasificacion_nueva}"


class CompraProducto(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_CONFIRMADA = "confirmada"
    ESTADO_RECIBIDA = "recibida"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_DEVUELTA = "devuelta"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"), (ESTADO_CONFIRMADA, "Confirmada"),
        (ESTADO_RECIBIDA, "Recibida"), (ESTADO_CANCELADA, "Cancelada"),
        (ESTADO_DEVUELTA, "Devuelta"),
    ]
    candidato = models.ForeignKey(CandidatoCompra, on_delete=models.PROTECT, related_name="compras")
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True)
    lote_captura = models.ForeignKey(LoteCaptura, on_delete=models.SET_NULL, null=True, blank=True)
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_compra = models.DateField()
    cantidad_comprada = models.PositiveIntegerField(default=1)
    precio_unitario_compra = models.DecimalField(max_digits=12, decimal_places=2)
    costo_envio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_comision = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    otros_costos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_unitario_real = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medio_pago = models.CharField(max_length=100, blank=True, null=True)
    proveedor_texto = models.CharField(max_length=200, blank=True, null=True)
    comprobante_texto = models.CharField(max_length=200, blank=True, null=True)
    url_compra = models.URLField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_CONFIRMADA)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_compra", "-id"]

    def save(self, *args, **kwargs):
        if self.cantidad_comprada <= 0:
            raise ValidationError({"cantidad_comprada": "La cantidad debe ser mayor a cero."})
        costos = [self.precio_unitario_compra, self.costo_envio, self.costo_comision, self.otros_costos]
        if any(valor < 0 for valor in costos):
            raise ValidationError("Los precios y costos no pueden ser negativos.")
        self.costo_total = self.cantidad_comprada * self.precio_unitario_compra + self.costo_envio + self.costo_comision + self.otros_costos
        self.costo_unitario_real = self.costo_total / self.cantidad_comprada
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Compra #{self.pk or 'nueva'} - {self.candidato}"


class PublicacionReventa(models.Model):
    CANAL_MARKETPLACE = "marketplace"
    CANAL_FACEBOOK = "facebook"
    CANAL_INSTAGRAM = "instagram"
    CANAL_WHATSAPP = "whatsapp"
    CANAL_LOCAL = "local"
    CANAL_MERCADO_LIBRE = "mercado_libre"
    CANAL_OTRO = "otro"
    CANAL_CHOICES = [(valor, label) for valor, label in [
        (CANAL_MARKETPLACE, "Marketplace"), (CANAL_FACEBOOK, "Facebook"),
        (CANAL_INSTAGRAM, "Instagram"), (CANAL_WHATSAPP, "WhatsApp"),
        (CANAL_LOCAL, "Local"), (CANAL_MERCADO_LIBRE, "Mercado Libre"), (CANAL_OTRO, "Otro"),
    ]]
    ESTADO_BORRADOR = "borrador"
    ESTADO_PUBLICADA = "publicada"
    ESTADO_PAUSADA = "pausada"
    ESTADO_VENDIDA_PARCIAL = "vendida_parcial"
    ESTADO_VENDIDA_TOTAL = "vendida_total"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_CHOICES = [(valor, label) for valor, label in [
        (ESTADO_BORRADOR, "Borrador"), (ESTADO_PUBLICADA, "Publicada"),
        (ESTADO_PAUSADA, "Pausada"), (ESTADO_VENDIDA_PARCIAL, "Vendida parcial"),
        (ESTADO_VENDIDA_TOTAL, "Vendida total"), (ESTADO_CANCELADA, "Cancelada"),
    ]]
    compra = models.ForeignKey(CompraProducto, on_delete=models.PROTECT, related_name="publicaciones")
    candidato = models.ForeignKey(CandidatoCompra, on_delete=models.SET_NULL, null=True, blank=True)
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True)
    canal = models.CharField(max_length=30, choices=CANAL_CHOICES)
    titulo_publicacion = models.CharField(max_length=250)
    fecha_publicacion = models.DateField()
    precio_publicado_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    cantidad_publicada = models.PositiveIntegerField(default=1)
    url_publicacion = models.URLField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PUBLICADA)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_publicacion", "-id"]

    def save(self, *args, **kwargs):
        if self.cantidad_publicada <= 0:
            raise ValidationError({"cantidad_publicada": "La cantidad debe ser mayor a cero."})
        if self.precio_publicado_unitario <= 0:
            raise ValidationError({"precio_publicado_unitario": "El precio debe ser mayor a cero."})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo_publicacion


class VentaProducto(models.Model):
    CANAL_CHOICES = PublicacionReventa.CANAL_CHOICES
    ESTADO_REGISTRADA = "registrada"
    ESTADO_CONFIRMADA = "confirmada"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_DEVUELTA = "devuelta"
    ESTADO_CHOICES = [
        (ESTADO_REGISTRADA, "Registrada"), (ESTADO_CONFIRMADA, "Confirmada"),
        (ESTADO_CANCELADA, "Cancelada"), (ESTADO_DEVUELTA, "Devuelta"),
    ]
    compra = models.ForeignKey(CompraProducto, on_delete=models.PROTECT, related_name="ventas")
    publicacion = models.ForeignKey(PublicacionReventa, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas")
    candidato = models.ForeignKey(CandidatoCompra, on_delete=models.SET_NULL, null=True, blank=True)
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_venta = models.DateField()
    cantidad_vendida = models.PositiveIntegerField(default=1)
    precio_unitario_venta = models.DecimalField(max_digits=12, decimal_places=2)
    ingreso_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_unitario_real = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_total_vendido = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    comision_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_envio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    otros_costos_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ganancia_neta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    canal_venta = models.CharField(max_length=30, choices=CANAL_CHOICES)
    comprador_texto = models.CharField(max_length=200, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_CONFIRMADA)
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_venta", "-id"]

    def save(self, *args, **kwargs):
        if self.cantidad_vendida <= 0:
            raise ValidationError({"cantidad_vendida": "La cantidad debe ser mayor a cero."})
        valores = [self.precio_unitario_venta, self.comision_venta, self.costo_envio_venta, self.otros_costos_venta]
        if any(valor < 0 for valor in valores):
            raise ValidationError("Los precios y costos no pueden ser negativos.")
        self.costo_unitario_real = self.compra.costo_unitario_real
        self.ingreso_bruto = self.cantidad_vendida * self.precio_unitario_venta
        self.costo_total_vendido = self.cantidad_vendida * self.costo_unitario_real
        self.ganancia_neta = self.ingreso_bruto - self.costo_total_vendido - self.comision_venta - self.costo_envio_venta - self.otros_costos_venta
        self.margen_pct = self.ganancia_neta / self.costo_total_vendido * 100 if self.costo_total_vendido > 0 else Decimal("0")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Venta #{self.pk or 'nueva'} - {self.compra}"


class ResultadoComercialProducto(models.Model):
    ESTADO_SIN_COMPRA = "sin_compra"
    ESTADO_COMPRADO_SIN_VENDER = "comprado_sin_vender"
    ESTADO_VENTA_PARCIAL = "venta_parcial"
    ESTADO_VENDIDO_CON_GANANCIA = "vendido_con_ganancia"
    ESTADO_VENDIDO_SIN_GANANCIA = "vendido_sin_ganancia"
    ESTADO_VENDIDO_CON_PERDIDA = "vendido_con_perdida"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_CHOICES = [(valor, label) for valor, label in [
        (ESTADO_SIN_COMPRA, "Sin compra"), (ESTADO_COMPRADO_SIN_VENDER, "Comprado sin vender"),
        (ESTADO_VENTA_PARCIAL, "Venta parcial"), (ESTADO_VENDIDO_CON_GANANCIA, "Vendido con ganancia"),
        (ESTADO_VENDIDO_SIN_GANANCIA, "Vendido sin ganancia"),
        (ESTADO_VENDIDO_CON_PERDIDA, "Vendido con perdida"), (ESTADO_DESCARTADO, "Descartado"),
    ]]
    candidato = models.OneToOneField(CandidatoCompra, on_delete=models.CASCADE, related_name="resultado_comercial")
    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.SET_NULL, null=True, blank=True)
    producto_canonico = models.ForeignKey(ProductoCanonico, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad_comprada_total = models.PositiveIntegerField(default=0)
    cantidad_vendida_total = models.PositiveIntegerField(default=0)
    cantidad_disponible = models.IntegerField(default=0)
    inversion_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ingreso_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ganancia_neta_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_real_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    precio_promedio_compra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_promedio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dias_hasta_primera_venta = models.PositiveIntegerField(null=True, blank=True)
    dias_hasta_venta_total = models.PositiveIntegerField(null=True, blank=True)
    estado_resultado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default=ESTADO_SIN_COMPRA)
    aprendizaje = models.TextField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Resultado {self.candidato}"
