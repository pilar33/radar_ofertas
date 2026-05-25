from django.db import models


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
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "producto por fuente"
        verbose_name_plural = "productos por fuente"
        ordering = ["-fecha_actualizacion"]

    def __str__(self):
        return self.titulo_original


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

    producto_fuente = models.ForeignKey(ProductoFuente, on_delete=models.CASCADE, related_name="precios_fuente")
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    precio_lista = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comparacion de precio"
        verbose_name_plural = "comparaciones de precio"
        ordering = ["-fecha_calculo"]

    def __str__(self):
        return f"{self.producto_canonico} - {self.fecha_calculo:%Y-%m-%d}"


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

    fuente_web = models.ForeignKey(FuenteWeb, on_delete=models.CASCADE, related_name="conectores")
    nombre = models.CharField(max_length=150)
    tipo_conector = models.CharField(max_length=30, choices=TIPO_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    descripcion = models.TextField(blank=True, null=True)
    frecuencia_sugerida = models.CharField(max_length=100, blank=True, null=True)
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
