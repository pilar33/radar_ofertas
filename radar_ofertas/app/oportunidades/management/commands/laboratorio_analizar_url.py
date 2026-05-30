from django.core.management.base import BaseCommand, CommandError

from oportunidades.services.laboratorio_mapeo_service import analizar_url_laboratorio


class Command(BaseCommand):
    help = "Analiza una URL en el laboratorio de mapeo sin guardar productos."

    def add_arguments(self, parser):
        parser.add_argument("--url", required=True)
        parser.add_argument("--limite", type=int, default=10)
        parser.add_argument("--modo", default="auto", choices=["auto", "json_ld", "css_selectors"])

    def handle(self, *args, **options):
        resultado = analizar_url_laboratorio(options["url"], limite=options["limite"], modo=options["modo"])
        if not resultado["url"]:
            raise CommandError(resultado["mensaje"])
        self.stdout.write(f"URL: {resultado['url']}")
        self.stdout.write(f"Status: {resultado['status_code']}")
        self.stdout.write(f"Mensaje: {resultado['mensaje']}")
        self.stdout.write(f"JSON-LD: {resultado['tiene_json_ld']}")
        self.stdout.write(f"JS probable: {resultado['requiere_js_probable']}")
        self.stdout.write("Bloqueos: " + (", ".join(resultado["bloqueos_detectados"]) or "-"))
        self.stdout.write(f"Productos detectados: {len(resultado['productos_detectados'])}")
        for item in resultado["productos_detectados"][: options["limite"]]:
            self.stdout.write(f"- {item.get('titulo') or '-'} | {item.get('precio_texto') or '-'} | score={item.get('score')}")
        self.stdout.write("Selectores sugeridos:")
        self.stdout.write(str(resultado["selectores_sugeridos"]))
