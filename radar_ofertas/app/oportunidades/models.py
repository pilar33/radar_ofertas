from decimal import Decimal
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.db import models

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
    palabra_clave = models.CharField(max_length=150)
    activa = models.BooleanField(default=True)
    prioridad = models.PositiveIntegerField(default=1)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "categoria de interes"
        verbose_name_plural = "categorias de interes"
        ordering = ["prioridad", "nombre"]

    def __str__(self):
        return self.nombre


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
    producto_canonico = models.ForeignKey(
        ProductoCanonico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="apariciones",
    )
    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.PROTECT, related_name="productos_fuente")
    categoria_fuente = models.ForeignKey(CategoriaFuente, on_delete=models.SET_NULL, null=True, blank=True)
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
    ESTADO_COMPRADO = "comprado"
    ESTADO_DESCARTADO = "descartado"
    ESTADO_CHOICES = [
        (ESTADO_OBSERVADO, "Observado"),
        (ESTADO_CANDIDATO, "Candidato"),
        (ESTADO_COMPRADO, "Comprado"),
        (ESTADO_DESCARTADO, "Descartado"),
    ]

    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.CASCADE, related_name="candidaturas_compra")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_CANDIDATO)
    precio_compra_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_reventa_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    porcentaje_margen_estimado = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    motivo = models.TextField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "candidato de compra"
        verbose_name_plural = "candidatos de compra"
        ordering = ["-fecha_actualizacion"]

    def __str__(self):
        return f"{self.producto_fuente} - {self.estado}"


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
        if self.max_productos and self.max_productos > 50:
            errores["max_productos"] = "En esta etapa el extractor no puede superar 50 productos."
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
