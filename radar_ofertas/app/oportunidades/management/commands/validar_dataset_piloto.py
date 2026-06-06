from django.core.management.base import BaseCommand

from oportunidades.services.validacion_dataset_service import validar_dataset_piloto


class Command(BaseCommand):
    help = "Valida la calidad minima del dataset piloto cargado en SQL Server local."

    def handle(self, *args, **options):
        resumen = validar_dataset_piloto()

        self.stdout.write("Validacion dataset piloto")
        self.stdout.write(f"Total productos procesados: {resumen['total_productos']}")
        self.stdout.write(f"Productos canonicos: {resumen['total_canonicos']}")
        self.stdout.write(f"Precios registrados: {resumen['total_precios']}")
        self.stdout.write(f"Fuentes: {resumen['total_fuentes']}")
        self.stdout.write(f"Con precio transferencia: {resumen['con_transferencia']}")
        self.stdout.write(f"Con imagen: {resumen['con_imagen']}")
        self.stdout.write(f"Con URL real: {resumen['con_url_real']}")
        self.stdout.write(f"Con precio oportunidad: {resumen['con_precio_oportunidad']}")
        self.stdout.write(f"Requieren revision: {resumen['requieren_revision']}")
        self.stdout.write(f"Duplicados probables: {resumen['duplicados_probables']}")
        self.stdout.write(f"Precio lista mayor a transferencia: {resumen['lista_mayor_transferencia']}")
        self.stdout.write(f"Dataset apto para analisis inicial: {'Si' if resumen['dataset_apto'] else 'No'}")

        if resumen["problemas"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Problemas detectados:"))
            for problema in resumen["problemas"]:
                self.stdout.write(f"- {problema}")
