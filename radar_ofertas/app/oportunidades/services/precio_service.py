def obtener_ultimo_precio(producto):
    return producto.precios.order_by("-fecha_relevamiento").first()
