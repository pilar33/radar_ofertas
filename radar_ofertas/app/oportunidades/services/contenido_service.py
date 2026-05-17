def generar_contenido_basico(oportunidad):
    producto = oportunidad.producto
    descuento_texto = f"margen estimado de {oportunidad.porcentaje_margen:.0f}%"

    return {
        "gancho": f"Este producto puede ser una oportunidad: {producto.titulo}",
        "guion_corto": (
            f"Hoy miramos {producto.titulo}. Precio actual: ${oportunidad.precio_actual}. "
            f"Precio estimado de reventa: ${oportunidad.precio_reventa_estimado}. "
            f"Segun el radar, tiene {descuento_texto}."
        ),
        "descripcion": (
            f"Oportunidad detectada en {producto.fuente.nombre} para la categoria "
            f"{producto.categoria.nombre}. Revisar disponibilidad, reputacion del vendedor y costos."
        ),
        "hashtags": "#ofertas #oportunidades #reventa #emprender #radarofertas",
    }
