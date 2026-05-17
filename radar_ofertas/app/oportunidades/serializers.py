from rest_framework import serializers

from .models import (
    CategoriaInteres,
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
