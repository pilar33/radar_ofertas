from dataclasses import dataclass
import re
import unicodedata

from oportunidades.models import CategoriaInteres


@dataclass(frozen=True)
class CategoriaBase:
    nombre: str
    slug: str
    prioridad: int
    palabras_clave: tuple
    marcas_clave: tuple = ()
    descripcion: str = ""


CATEGORIAS_BASE = [
    CategoriaBase(
        "Materiales de obra",
        "materiales-de-obra",
        10,
        ("cemento", "ladrillo", "arena", "cal", "hierro", "chapa", "membrana", "pintura obra"),
    ),
    CategoriaBase(
        "Herramientas",
        "herramientas",
        20,
        ("taladro", "amoladora", "atornillador", "sierra", "herramienta", "llave", "pinza"),
    ),
    CategoriaBase(
        "Electrodomesticos",
        "electrodomesticos",
        30,
        ("heladera", "lavarropas", "cocina", "microondas", "pava electrica", "freidora", "aire acondicionado"),
    ),
    CategoriaBase(
        "Hogar",
        "hogar",
        40,
        ("hogar", "bazar", "cocina", "decoracion", "alfombra", "organizador"),
    ),
    CategoriaBase(
        "Vestimenta",
        "vestimenta",
        50,
        ("bambu", "remera", "camisa", "pantalon", "campera", "buzo"),
        ("Bambu",),
    ),
    CategoriaBase(
        "Calzado",
        "calzado",
        60,
        ("zapatilla", "botin", "bota", "borcego", "calzado", "sandalia"),
    ),
    CategoriaBase(
        "Ropa de trabajo",
        "ropa-de-trabajo",
        70,
        ("ropa de trabajo", "camisa de trabajo", "pantalon cargo", "campera de trabajo", "seguridad industrial"),
        ("Pampero", "Ombu", "Grafa"),
    ),
    CategoriaBase(
        "Tecnologia",
        "tecnologia",
        80,
        ("notebook", "celular", "tablet", "monitor", "auricular", "tecnologia"),
    ),
    CategoriaBase(
        "Muebles",
        "muebles",
        90,
        ("silla", "mesa", "placard", "mueble", "rack"),
    ),
    CategoriaBase(
        "Jardin",
        "jardin",
        100,
        ("jardin", "pileta", "manguera", "cortadora de cesped", "riego"),
    ),
    CategoriaBase("Otros", "otros", 999, ("otros", "sin clasificar")),
]


def _texto_clasificacion(*partes):
    texto = " ".join(str(parte or "") for parte in partes).lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _coincide(texto, terminos):
    texto = f" {texto} "
    for termino in terminos:
        normalizado = _texto_clasificacion(termino)
        if normalizado and normalizado in texto:
            return True
    return False


def asegurar_categorias_base():
    creadas = 0
    actualizadas = 0
    for base in CATEGORIAS_BASE:
        categoria = CategoriaInteres.objects.filter(slug=base.slug).first()
        if not categoria:
            categoria = CategoriaInteres.objects.filter(nombre__iexact=base.nombre).first()
        defaults = {
            "slug": base.slug,
            "palabra_clave": base.palabras_clave[0] if base.palabras_clave else base.nombre.lower(),
            "descripcion": base.descripcion,
            "activa": True,
            "prioridad": base.prioridad,
            "palabras_clave": ", ".join(base.palabras_clave),
            "marcas_clave": ", ".join(base.marcas_clave),
        }
        if categoria:
            for campo, valor in defaults.items():
                if not getattr(categoria, campo):
                    setattr(categoria, campo, valor)
            categoria.save()
            actualizadas += 1
        else:
            CategoriaInteres.objects.create(nombre=base.nombre, **defaults)
            creadas += 1
    return {"creadas": creadas, "actualizadas": actualizadas}


def obtener_categoria_otros():
    asegurar_categorias_base()
    return CategoriaInteres.objects.filter(slug="otros").first()


def clasificar_categoria_producto(
    titulo="",
    categoria_original="",
    descripcion="",
    marca="",
    fuente=None,
    categoria_default=None,
):
    texto = _texto_clasificacion(
        categoria_original,
        titulo,
        descripcion,
        marca,
        getattr(fuente, "nombre", ""),
        getattr(fuente, "rubro_principal", ""),
    )
    if categoria_original:
        existente = CategoriaInteres.objects.filter(nombre__iexact=str(categoria_original).strip()).first()
        if existente:
            return existente
    if categoria_default:
        return categoria_default

    asegurar_categorias_base()
    categorias_por_slug = {categoria.slug: categoria for categoria in CategoriaInteres.objects.filter(activa=True)}
    reglas = [
        ("calzado", ("zapatilla", "botin", "bota", "borcego", "calzado", "sandalia")),
        ("ropa-de-trabajo", ("pampero", "ombu", "grafa", "ropa de trabajo", "camisa de trabajo", "pantalon cargo", "campera de trabajo")),
        ("herramientas", ("taladro", "amoladora", "atornillador", "sierra", "herramienta", "llave", "pinza")),
        ("materiales-de-obra", ("cemento", "ladrillo", "arena", "cal", "hierro", "chapa", "membrana", "pintura obra")),
        ("electrodomesticos", ("heladera", "lavarropas", "cocina", "microondas", "pava electrica", "freidora", "aire acondicionado")),
        ("vestimenta", ("bambu", "remera", "camisa", "pantalon", "campera", "buzo")),
        ("muebles", ("silla", "mesa", "placard", "mueble", "rack")),
        ("jardin", ("jardin", "pileta", "manguera", "cortadora de cesped", "riego")),
    ]
    for slug, terminos in reglas:
        if _coincide(texto, terminos) and slug in categorias_por_slug:
            return categorias_por_slug[slug]

    for categoria in CategoriaInteres.objects.filter(activa=True).order_by("prioridad", "nombre"):
        terminos = []
        if categoria.palabras_clave:
            terminos.extend(categoria.palabras_clave.split(","))
        if categoria.marcas_clave:
            terminos.extend(categoria.marcas_clave.split(","))
        if _coincide(texto, terminos):
            return categoria

    return categorias_por_slug.get("otros") or obtener_categoria_otros()
