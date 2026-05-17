from rest_framework import serializers

from .models import (
    CategoriaInteres,
    ConsultaMercadoLibre,
    ContenidoSugerido,
    FuenteProducto,
    Oportunidad,
    PrecioProducto,
    Producto,
    Publicacion,
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
