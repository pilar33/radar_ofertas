HASHTAGS_POR_CATEGORIA = {
    "Cocina/Emprendimiento": "#emprenderencasa #cocina #comprasutiles",
    "Organizacion": "#organizacion #hogar #comprasinteligentes",
    "Organización": "#organizacion #hogar #comprasinteligentes",
    "Tecnologia economica": "#tecnologia #gadgets #ofertasargentina",
    "Tecnología económica": "#tecnologia #gadgets #ofertasargentina",
    "Seguridad": "#seguridad #hogarseguro #comprasutiles",
    "Hogar": "#hogar #deco #comprasutiles",
}

HASHTAGS_BASE = "#argentina #mercadolibre #ofertas"


def _hashtags_categoria(categoria):
    nombre = getattr(categoria, "nombre", "")
    return HASHTAGS_POR_CATEGORIA.get(nombre, "#comprasutiles #ofertasargentina")


def generar_contenido_basico(oportunidad):
    producto = oportunidad.producto
    categoria_hashtags = _hashtags_categoria(producto.categoria)

    if oportunidad.tipo == "reventa":
        gancho = "Este producto puede servir si estas pensando en emprender desde casa."
        guion = (
            f"Hoy encontramos {producto.titulo}. Es chico, facil de mover y tiene un margen estimado "
            f"de {oportunidad.porcentaje_margen:.2f}%. Puede ser interesante para probar reventa con bajo volumen."
        )
        descripcion = (
            f"Oportunidad detectada en {producto.fuente.nombre}. Revisar stock, costos finales y reputacion "
            "del vendedor antes de comprar para reventa."
        )
    elif oportunidad.tipo == "afiliado":
        gancho = "Encontre una compra util para quienes quieren organizar mejor la casa."
        guion = (
            f"Si estabas buscando algo practico, {producto.titulo} puede ser una buena opcion. "
            "El radar lo marca mas interesante para recomendar que para comprar stock."
        )
        descripcion = (
            "Producto util para contenido, comparativas o recomendacion. Conviene validar precio, envio "
            "y opiniones antes de publicarlo."
        )
    else:
        gancho = "Antes de comprar algo parecido, revisa si realmente te conviene."
        guion = (
            f"{producto.titulo} no queda priorizado por el radar en este momento. "
            "El margen, el riesgo o los datos disponibles no justifican una publicacion comercial fuerte."
        )
        descripcion = "No se recomienda publicar este producto como oportunidad hasta revisar mejores condiciones."

    return {
        "gancho": gancho,
        "guion_corto": guion,
        "descripcion": descripcion,
        "hashtags": f"{categoria_hashtags} {HASHTAGS_BASE}",
    }
