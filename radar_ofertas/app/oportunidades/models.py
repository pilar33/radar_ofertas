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
    mensaje_error = models.TextField(blank=True, null=True)
    fecha_consulta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "consulta de Mercado Libre"
        verbose_name_plural = "consultas de Mercado Libre"
        ordering = ["-fecha_consulta"]

    def __str__(self):
        return f"{self.query} ({self.site_id})"


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
