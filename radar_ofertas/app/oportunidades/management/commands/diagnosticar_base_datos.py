from django.core.management.base import BaseCommand

from oportunidades.services.base_datos_service import obtener_diagnostico_base_datos


class Command(BaseCommand):
    help = "Muestra el motor de base de datos activo y conteos principales sin exponer secretos."

    def handle(self, *args, **options):
        diagnostico = obtener_diagnostico_base_datos()

        self.stdout.write("Diagnostico de base de datos")
        self.stdout.write(f"Engine: {diagnostico['engine']}")
        self.stdout.write(f"Vendor: {diagnostico['vendor']}")
        self.stdout.write(f"Base: {diagnostico['name']}")
        self.stdout.write(f"Host: {diagnostico['host'] or '-'}")
        self.stdout.write(f"Puerto: {diagnostico['port'] or '-'}")
        self.stdout.write(f"SQLite: {diagnostico['resumen']['SQLite']}")
        self.stdout.write(f"SQL Server: {diagnostico['resumen']['SQL Server']}")
        self.stdout.write(f"Render: {diagnostico['resumen']['Render']}")
        self.stdout.write(f"Persistente: {diagnostico['resumen']['Persistente']}")

        if diagnostico["advertencia"]:
            self.stdout.write(self.style.WARNING(f"Advertencia: {diagnostico['advertencia']}"))
        self.stdout.write(f"Recomendacion: {diagnostico['recomendacion']}")

        self.stdout.write("")
        self.stdout.write("Conteos principales:")
        for nombre, cantidad in diagnostico["conteos"].items():
            valor = cantidad if cantidad is not None else "no disponible"
            self.stdout.write(f"- {nombre}: {valor}")
