from rest_framework import serializers

from .models import (
    AuditoriaFuenteWeb,
    CategoriaInteres,
    CategoriaFuente,
    ComercioLocal,
    ComparacionPrecio,
    ConectorFuente,
    ConfiguracionExtractorWeb,
    ConsultaMercadoLibre,
    ContenidoSugerido,
    DecisionTecnica,
    DetalleImportacionProducto,
    DetalleEjecucionConector,
    EjecucionConector,
    EvaluacionOportunidadMultifuente,
    FuenteProducto,
    FuenteWeb,
    ImportacionProductos,
    ItemRanking,
    LoteCapturaLocal,
    LoteRanking,
    ObjetivoVigilanciaLocal,
    ObservacionPrecioLocal,
    Oportunidad,
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
    UmbralPrecioLocal,
)


class FuenteProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuenteProducto
        fields = "__all__"


class CategoriaInteresSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaInteres
        fields = "__all__"


class ProductoSerializer(serializers.ModelSerializer):
    fuente = FuenteProductoSerializer(read_only=True)
    categoria = CategoriaInteresSerializer(read_only=True)

    class Meta:
        model = Producto
        fields = "__all__"


class PrecioProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrecioProducto
        fields = "__all__"


class ContenidoSugeridoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContenidoSugerido
        fields = "__all__"


class PublicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publicacion
        fields = "__all__"


class ConsultaMercadoLibreSerializer(serializers.ModelSerializer):
    categoria = CategoriaInteresSerializer(read_only=True)

    class Meta:
        model = ConsultaMercadoLibre
        fields = "__all__"


class MeliSincronizarSerializer(serializers.Serializer):
    query = serializers.CharField(required=False, allow_blank=True, max_length=255)
    categoria_id = serializers.IntegerField(required=False, allow_null=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)
    usar_token_si_existe = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        query = attrs.get("query")
        categoria_id = attrs.get("categoria_id")

        if not query and not categoria_id:
            raise serializers.ValidationError("Se requiere query o categoria_id.")

        return attrs


class OportunidadSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer(read_only=True)

    class Meta:
        model = Oportunidad
        fields = "__all__"


class OportunidadDetalleSerializer(serializers.ModelSerializer):
    producto = ProductoSerializer(read_only=True)
    contenidos = ContenidoSugeridoSerializer(many=True, read_only=True)
    publicaciones = PublicacionSerializer(many=True, read_only=True)

    class Meta:
        model = Oportunidad
        fields = "__all__"


class OportunidadEstadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Oportunidad
        fields = ["estado"]


class PoliticaExtraccionFuenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PoliticaExtraccionFuente
        fields = "__all__"


class FuenteWebSerializer(serializers.ModelSerializer):
    politica_extraccion = PoliticaExtraccionFuenteSerializer(read_only=True)

    class Meta:
        model = FuenteWeb
        fields = "__all__"


class CategoriaFuenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaFuente
        fields = "__all__"


class ProductoCanonicoSerializer(serializers.ModelSerializer):
    categoria = CategoriaInteresSerializer(read_only=True)

    class Meta:
        model = ProductoCanonico
        fields = "__all__"


class ProductoMultifuenteSerializer(serializers.ModelSerializer):
    categoria = CategoriaInteresSerializer(read_only=True)
    cantidad_fuentes = serializers.SerializerMethodField()
    precio_minimo = serializers.SerializerMethodField()
    precio_promedio = serializers.SerializerMethodField()
    indice_oportunidad = serializers.SerializerMethodField()
    tipo_sugerido = serializers.SerializerMethodField()

    class Meta:
        model = ProductoCanonico
        fields = [
            "id",
            "nombre_normalizado",
            "categoria",
            "marca",
            "modelo",
            "es_chico_liviano",
            "es_fragil",
            "cantidad_fuentes",
            "precio_minimo",
            "precio_promedio",
            "indice_oportunidad",
            "tipo_sugerido",
        ]

    def _ultima_comparacion(self, obj):
        return obj.comparaciones.order_by("-fecha_calculo", "-id").first()

    def _ultima_evaluacion(self, obj):
        return obj.evaluaciones_multifuente.order_by("-fecha_creacion", "-id").first()

    def get_cantidad_fuentes(self, obj):
        comparacion = self._ultima_comparacion(obj)
        return comparacion.cantidad_fuentes if comparacion else 0

    def get_precio_minimo(self, obj):
        comparacion = self._ultima_comparacion(obj)
        return comparacion.precio_minimo if comparacion else None

    def get_precio_promedio(self, obj):
        comparacion = self._ultima_comparacion(obj)
        return comparacion.precio_promedio if comparacion else None

    def get_indice_oportunidad(self, obj):
        evaluacion = self._ultima_evaluacion(obj)
        return evaluacion.indice_oportunidad if evaluacion else None

    def get_tipo_sugerido(self, obj):
        evaluacion = self._ultima_evaluacion(obj)
        return evaluacion.tipo if evaluacion else None


class ProductoFuenteSerializer(serializers.ModelSerializer):
    fuente_web = FuenteWebSerializer(read_only=True)
    categoria_fuente = CategoriaFuenteSerializer(read_only=True)
    producto_canonico = ProductoCanonicoSerializer(read_only=True)
    categoria_normalizada = serializers.SerializerMethodField()

    class Meta:
        model = ProductoFuente
        fields = "__all__"

    def get_categoria_normalizada(self, obj):
        categoria = None
        if obj.producto_canonico_id:
            categoria = obj.producto_canonico.categoria
        elif obj.categoria_fuente_id:
            categoria = obj.categoria_fuente.categoria_normalizada
        return CategoriaInteresSerializer(categoria).data if categoria else None


class LoteRankingSerializer(serializers.ModelSerializer):
    categoria = CategoriaInteresSerializer(read_only=True)

    class Meta:
        model = LoteRanking
        fields = "__all__"


class ItemRankingSerializer(serializers.ModelSerializer):
    lote = LoteRankingSerializer(read_only=True)
    categoria = CategoriaInteresSerializer(read_only=True)
    producto_fuente = ProductoFuenteSerializer(read_only=True)

    class Meta:
        model = ItemRanking
        fields = "__all__"


class ComercioLocalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComercioLocal
        fields = "__all__"


class LoteCapturaLocalSerializer(serializers.ModelSerializer):
    comercio = ComercioLocalSerializer(read_only=True)

    class Meta:
        model = LoteCapturaLocal
        fields = "__all__"


class UmbralPrecioLocalSerializer(serializers.ModelSerializer):
    categoria = CategoriaInteresSerializer(read_only=True)
    producto_canonico = ProductoCanonicoSerializer(read_only=True)

    class Meta:
        model = UmbralPrecioLocal
        fields = "__all__"


class ObservacionPrecioLocalSerializer(serializers.ModelSerializer):
    comercio = ComercioLocalSerializer(read_only=True)
    categoria = CategoriaInteresSerializer(read_only=True)
    lote = LoteCapturaLocalSerializer(read_only=True)
    umbral_aplicado = UmbralPrecioLocalSerializer(read_only=True)

    class Meta:
        model = ObservacionPrecioLocal
        fields = "__all__"


class ObjetivoVigilanciaLocalSerializer(serializers.ModelSerializer):
    comercio = ComercioLocalSerializer(read_only=True)
    categoria = CategoriaInteresSerializer(read_only=True)
    lote = LoteCapturaLocalSerializer(read_only=True)

    class Meta:
        model = ObjetivoVigilanciaLocal
        fields = "__all__"


class PrecioFuenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrecioFuente
        fields = "__all__"


class ComparacionPrecioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComparacionPrecio
        fields = "__all__"


class EvaluacionOportunidadMultifuenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluacionOportunidadMultifuente
        fields = "__all__"


class DecisionTecnicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionTecnica
        fields = "__all__"


class ConectorFuenteSerializer(serializers.ModelSerializer):
    fuente_web = FuenteWebSerializer(read_only=True)
    validacion = serializers.SerializerMethodField()

    class Meta:
        model = ConectorFuente
        fields = "__all__"

    def get_validacion(self, obj):
        from oportunidades.services.conectores_service import validar_conector_segun_politica

        return validar_conector_segun_politica(obj)


class EjecucionConectorSerializer(serializers.ModelSerializer):
    conector = ConectorFuenteSerializer(read_only=True)

    class Meta:
        model = EjecucionConector
        fields = "__all__"


class DetalleEjecucionConectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleEjecucionConector
        fields = "__all__"


class RecursoFuenteDetectadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecursoFuenteDetectado
        fields = "__all__"


class AuditoriaFuenteWebSerializer(serializers.ModelSerializer):
    fuente_web = FuenteWebSerializer(read_only=True)
    recursos = RecursoFuenteDetectadoSerializer(many=True, read_only=True)

    class Meta:
        model = AuditoriaFuenteWeb
        fields = "__all__"


class ConfiguracionExtractorWebSerializer(serializers.ModelSerializer):
    conector = ConectorFuenteSerializer(read_only=True)

    class Meta:
        model = ConfiguracionExtractorWeb
        fields = "__all__"


class ResultadoExtraccionWebSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultadoExtraccionWeb
        fields = "__all__"


class ResultadoLaboratorioMapeoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultadoLaboratorioMapeo
        fields = "__all__"


class SesionLaboratorioMapeoSerializer(serializers.ModelSerializer):
    resultados = ResultadoLaboratorioMapeoSerializer(many=True, read_only=True)

    class Meta:
        model = SesionLaboratorioMapeo
        fields = "__all__"


class RevisionManualFuenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevisionManualFuente
        fields = "__all__"


class DetalleImportacionProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleImportacionProducto
        fields = "__all__"


class ImportacionProductosSerializer(serializers.ModelSerializer):
    fuente_web = FuenteWebSerializer(read_only=True)
    detalles = DetalleImportacionProductoSerializer(many=True, read_only=True)

    class Meta:
        model = ImportacionProductos
        fields = "__all__"


class ImportacionProductosCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportacionProductos
        fields = ["id", "fuente_web", "archivo", "observaciones"]


class CargaProductoURLSerializer(serializers.Serializer):
    fuente_web = serializers.PrimaryKeyRelatedField(queryset=FuenteWeb.objects.filter(activa=True))
    url_producto = serializers.URLField()
    titulo = serializers.CharField(max_length=255)
    precio = serializers.CharField()
    categoria = serializers.PrimaryKeyRelatedField(queryset=CategoriaInteres.objects.filter(activa=True))
    marca = serializers.CharField(required=False, allow_blank=True)
    descripcion = serializers.CharField(required=False, allow_blank=True)
    imagen_url = serializers.URLField(required=False, allow_blank=True)
    precio_lista = serializers.CharField(required=False, allow_blank=True)
    costo_envio = serializers.CharField(required=False, allow_blank=True)
    moneda = serializers.CharField(required=False, default="ARS")
    es_chico_liviano = serializers.BooleanField(required=False, default=False)
    es_fragil = serializers.BooleanField(required=False, default=False)
    observaciones = serializers.CharField(required=False, allow_blank=True)
