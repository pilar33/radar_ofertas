from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Muestra la guia operativa para cargar una fuente piloto real de forma controlada."

    def add_arguments(self, parser):
        parser.add_argument("--fuente", default="Ganga Home")
        parser.add_argument("--limite", type=int, default=20)

    def handle(self, *args, **options):
        fuente = options["fuente"]
        limite = min(options["limite"], 20)

        self.stdout.write(f"Flujo piloto para fuente: {fuente}")
        self.stdout.write(f"Limite recomendado: {limite} productos")
        self.stdout.write("")
        pasos = [
            "Abrir /sistema/base-datos/ y confirmar SQL Server local, no Render SQLite.",
            "Abrir /laboratorio/mapeo-web/.",
            f"Pegar una URL real de categoria/listado de {fuente}.",
            "Analizar pagina.",
            "Verificar titulo, URL, imagen, precio lista, transferencia, tarjeta/cuotas y precio oportunidad.",
            "Guardar extractor si todavia no esta guardado.",
            "Ejecutar preview controlado.",
            f"Seleccionar como maximo {limite} productos.",
            "Procesar seleccionados.",
            "Ir a /curaduria/dashboard/ y revisar productos.",
            "Ejecutar recalcular_ranking_comercial.",
            "Validar /dataset/validacion-piloto/.",
            "Exportar dataset y snapshot de respaldo.",
        ]
        for indice, paso in enumerate(pasos, start=1):
            self.stdout.write(f"{indice}. {paso}")
