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


CATEGORIA_SUPERMERCADO = CategoriaBase(
    "Supermercado, bebidas y mercaderia revendible",
    "supermercado-bebidas-mercaderia-revendible",
    35,
    ("supermercado", "bebidas", "mercaderia revendible", "fardo", "pack"),
)


SUBCATEGORIAS_SUPERMERCADO = [
    CategoriaBase("Gaseosas", "gaseosas", 351, ("gaseosa", "coca", "cola", "cunnington", "sprite", "fanta")),
    CategoriaBase("Aguas y aguas saborizadas", "aguas-aguas-saborizadas", 352, ("agua", "agua saborizada")),
    CategoriaBase("Jugos", "jugos", 353, ("jugo", "nectar")),
    CategoriaBase("Cervezas", "cervezas", 354, ("cerveza", "lata", "porron")),
    CategoriaBase("Energizantes", "energizantes", 355, ("energizante", "speed", "red bull", "monster")),
    CategoriaBase("Almacen revendible", "almacen-revendible", 356, ("almacen", "arroz", "fideo", "aceite", "yerba", "azucar")),
    CategoriaBase("Limpieza", "limpieza", 357, ("limpieza", "detergente", "lavandina", "jabon")),
    CategoriaBase("Higiene personal", "higiene-personal", 358, ("higiene", "shampoo", "desodorante", "pasta dental")),
    CategoriaBase("Papel y panales", "papel-panales", 359, ("papel", "panal", "panales", "rollo")),
    CategoriaBase("Otros productos de supermercado", "otros-productos-supermercado", 360, ("otros supermercado",)),
]


CATEGORIA_MERCADERIA_LOCAL = CategoriaBase(
    "Mercaderia local de oportunidad",
    "mercaderia-local-oportunidad",
    36,
    ("mercaderia local", "salta capital", "mayorista local", "precio local"),
    descripcion="Categoria para oportunidades observadas manualmente en comercios fisicos de Salta.",
)


SUBCATEGORIAS_MERCADERIA_LOCAL = [
    CategoriaBase("Alimento economico", "alimento-economico", 361, ("fideo", "arroz", "polenta", "harina", "azucar")),
    CategoriaBase("Alimento economico para consumo familiar", "alimento-economico-consumo-familiar", 362, ("consumo familiar", "comida economica")),
    CategoriaBase("Alimento para perros/pichos", "alimento-para-perros-pichos", 363, ("perro", "picho", "animal", "menudo", "carcasa")),
    CategoriaBase("Menudos, carcasas y recortes", "menudos-carcasas-recortes", 364, ("menudo", "carcasa", "recorte")),
    CategoriaBase("Fardos y bultos", "fardos-bultos", 365, ("fardo", "bulto", "caja")),
    CategoriaBase("Segundas marcas", "segundas-marcas", 366, ("segunda marca", "economico")),
    CategoriaBase("Liquidaciones locales", "liquidaciones-locales", 367, ("liquidacion", "remate", "oferta local")),
    CategoriaBase("Supermercado fisico Salta", "supermercado-fisico-salta", 368, ("supermercado fisico", "gondola", "vea fisico")),
    CategoriaBase("Mayoristas locales", "mayoristas-locales", 369, ("mayorista", "calle oran")),
    CategoriaBase("Bebidas y distribuidoras", "bebidas-distribuidoras", 370, ("bebida", "aceite", "distribuidora")),
    CategoriaBase("Almacen", "almacen-local", 371, ("almacen", "arroz", "fideos", "harina")),
    CategoriaBase("Limpieza", "limpieza-local", 372, ("limpieza", "detergente", "lavandina")),
    CategoriaBase("Higiene", "higiene-local", 373, ("higiene", "jabon", "shampoo")),
    CategoriaBase("Papel higienico y papel de cocina", "papel-higienico-papel-cocina", 374, ("papel higienico", "papel cocina", "rollo")),
    CategoriaBase("Mercaderia para stock", "mercaderia-para-stock", 375, ("stock", "guardar", "familiar")),
    CategoriaBase("Mercaderia para posible reventa", "mercaderia-para-posible-reventa", 376, ("reventa", "revender")),
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


def asegurar_categorias_supermercado():
    resumen = asegurar_categorias_base()
    padre = CategoriaInteres.objects.filter(slug=CATEGORIA_SUPERMERCADO.slug).first()
    if not padre:
        padre = CategoriaInteres.objects.filter(nombre__iexact=CATEGORIA_SUPERMERCADO.nombre).first()
    defaults_padre = {
        "slug": CATEGORIA_SUPERMERCADO.slug,
        "palabra_clave": "supermercado",
        "descripcion": "Categoria para bebidas, consumo masivo y mercaderia revendible.",
        "activa": True,
        "prioridad": CATEGORIA_SUPERMERCADO.prioridad,
        "palabras_clave": ", ".join(CATEGORIA_SUPERMERCADO.palabras_clave),
        "marcas_clave": "",
    }
    if padre:
        for campo, valor in defaults_padre.items():
            if not getattr(padre, campo):
                setattr(padre, campo, valor)
        padre.save()
        resumen["actualizadas"] += 1
    else:
        padre = CategoriaInteres.objects.create(nombre=CATEGORIA_SUPERMERCADO.nombre, **defaults_padre)
        resumen["creadas"] += 1

    for base in SUBCATEGORIAS_SUPERMERCADO:
        categoria = CategoriaInteres.objects.filter(slug=base.slug).first()
        if not categoria:
            categoria = CategoriaInteres.objects.filter(nombre__iexact=base.nombre).first()
        defaults = {
            "slug": base.slug,
            "palabra_clave": base.palabras_clave[0],
            "descripcion": base.descripcion,
            "activa": True,
            "prioridad": base.prioridad,
            "categoria_padre": padre,
            "palabras_clave": ", ".join(base.palabras_clave),
            "marcas_clave": ", ".join(base.marcas_clave),
        }
        if categoria:
            for campo, valor in defaults.items():
                if campo == "categoria_padre" or not getattr(categoria, campo):
                    setattr(categoria, campo, valor)
            categoria.save()
            resumen["actualizadas"] += 1
        else:
            CategoriaInteres.objects.create(nombre=base.nombre, **defaults)
            resumen["creadas"] += 1
    return resumen


def asegurar_categorias_mercaderia_local():
    resumen = asegurar_categorias_supermercado()
    padre = CategoriaInteres.objects.filter(slug=CATEGORIA_MERCADERIA_LOCAL.slug).first()
    if not padre:
        padre = CategoriaInteres.objects.filter(nombre__iexact=CATEGORIA_MERCADERIA_LOCAL.nombre).first()
    defaults_padre = {
        "slug": CATEGORIA_MERCADERIA_LOCAL.slug,
        "palabra_clave": "mercaderia local",
        "descripcion": CATEGORIA_MERCADERIA_LOCAL.descripcion,
        "activa": True,
        "prioridad": CATEGORIA_MERCADERIA_LOCAL.prioridad,
        "palabras_clave": ", ".join(CATEGORIA_MERCADERIA_LOCAL.palabras_clave),
        "marcas_clave": "",
    }
    if padre:
        for campo, valor in defaults_padre.items():
            if not getattr(padre, campo):
                setattr(padre, campo, valor)
        padre.save()
        resumen["actualizadas"] += 1
    else:
        padre = CategoriaInteres.objects.create(nombre=CATEGORIA_MERCADERIA_LOCAL.nombre, **defaults_padre)
        resumen["creadas"] += 1

    for base in SUBCATEGORIAS_MERCADERIA_LOCAL:
        categoria = CategoriaInteres.objects.filter(slug=base.slug).first()
        if not categoria:
            categoria = CategoriaInteres.objects.filter(nombre__iexact=base.nombre).first()
        defaults = {
            "slug": base.slug,
            "palabra_clave": base.palabras_clave[0],
            "descripcion": base.descripcion,
            "activa": True,
            "prioridad": base.prioridad,
            "categoria_padre": padre,
            "palabras_clave": ", ".join(base.palabras_clave),
            "marcas_clave": ", ".join(base.marcas_clave),
        }
        if categoria:
            for campo, valor in defaults.items():
                if campo == "categoria_padre" or not getattr(categoria, campo):
                    setattr(categoria, campo, valor)
            categoria.save()
            resumen["actualizadas"] += 1
        else:
            CategoriaInteres.objects.create(nombre=base.nombre, **defaults)
            resumen["creadas"] += 1
    return resumen


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
        ("gaseosas", ("gaseosa", "coca cola", "coca", "cunnington", "sprite", "fanta", "cola")),
        ("aguas-aguas-saborizadas", ("agua", "agua saborizada")),
        ("jugos", ("jugo", "nectar")),
        ("cervezas", ("cerveza", "lata cerveza", "porron")),
        ("energizantes", ("energizante", "speed", "red bull", "monster")),
        ("almacen-revendible", ("arroz", "fideo", "aceite", "yerba", "azucar", "almacen")),
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
