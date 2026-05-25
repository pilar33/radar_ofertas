import re


def normalizar_texto_producto(texto):
    texto = (texto or "").lower()
    texto = re.sub(r"[^a-z0-9áéíóúñü\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def sugerir_producto_canonico(producto_fuente):
    if not producto_fuente:
        return None
    return normalizar_texto_producto(producto_fuente.titulo_original)


def calcular_similitud_basica(producto_a, producto_b):
    palabras_a = set(normalizar_texto_producto(producto_a).split())
    palabras_b = set(normalizar_texto_producto(producto_b).split())
    if not palabras_a or not palabras_b:
        return 0
    interseccion = palabras_a.intersection(palabras_b)
    union = palabras_a.union(palabras_b)
    return round((len(interseccion) / len(union)) * 100, 2)
