from django.db import migrations
from django.utils.text import slugify


CATEGORIAS_BASE = [
    ("Materiales de obra", "materiales-de-obra", 10, "cemento, ladrillo, arena, cal, hierro, chapa, membrana, pintura obra", ""),
    ("Herramientas", "herramientas", 20, "taladro, amoladora, atornillador, sierra, herramienta, llave, pinza", ""),
    ("Electrodomesticos", "electrodomesticos", 30, "heladera, lavarropas, cocina, microondas, pava electrica, freidora, aire acondicionado", ""),
    ("Hogar", "hogar", 40, "hogar, bazar, cocina, decoracion, alfombra, organizador", ""),
    ("Vestimenta", "vestimenta", 50, "bambu, remera, camisa, pantalon, campera, buzo", "Bambu"),
    ("Calzado", "calzado", 60, "zapatilla, botin, bota, borcego, calzado, sandalia", ""),
    ("Ropa de trabajo", "ropa-de-trabajo", 70, "ropa de trabajo, camisa de trabajo, pantalon cargo, campera de trabajo, seguridad industrial", "Pampero, Ombu, Grafa"),
    ("Tecnologia", "tecnologia", 80, "notebook, celular, tablet, monitor, auricular, tecnologia", ""),
    ("Muebles", "muebles", 90, "silla, mesa, placard, mueble, rack", ""),
    ("Jardin", "jardin", 100, "jardin, pileta, manguera, cortadora de cesped, riego", ""),
    ("Otros", "otros", 999, "otros, sin clasificar", ""),
]


def cargar_categorias_base(apps, schema_editor):
    CategoriaInteres = apps.get_model("oportunidades", "CategoriaInteres")

    for categoria in CategoriaInteres.objects.all():
        if not categoria.slug:
            categoria.slug = slugify(categoria.nombre)
            categoria.save(update_fields=["slug"])

    for nombre, slug, prioridad, palabras_clave, marcas_clave in CATEGORIAS_BASE:
        categoria = CategoriaInteres.objects.filter(slug=slug).first()
        if not categoria:
            categoria = CategoriaInteres.objects.filter(nombre__iexact=nombre).first()
        defaults = {
            "slug": slug,
            "palabra_clave": palabras_clave.split(",")[0].strip(),
            "activa": True,
            "prioridad": prioridad,
            "palabras_clave": palabras_clave,
            "marcas_clave": marcas_clave or None,
        }
        if categoria:
            for campo, valor in defaults.items():
                if not getattr(categoria, campo):
                    setattr(categoria, campo, valor)
            categoria.save()
        else:
            CategoriaInteres.objects.create(nombre=nombre, **defaults)


class Migration(migrations.Migration):

    dependencies = [
        ("oportunidades", "0022_categoriainteres_categoria_padre_and_more"),
    ]

    operations = [
        migrations.RunPython(cargar_categorias_base, migrations.RunPython.noop),
    ]
