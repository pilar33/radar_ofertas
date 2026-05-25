from django.core.management.base import BaseCommand

from oportunidades.services.storage_service import diagnosticar_storage_config


class Command(BaseCommand):
    help = "Muestra diagnostico de storage sin exponer secretos."

    def handle(self, *args, **options):
        diagnostico = diagnosticar_storage_config()
        self.stdout.write(f"Render: {'Si' if diagnostico['render'] else 'No'}")
        self.stdout.write(f"USE_EXTERNAL_STORAGE: {'Si' if diagnostico['use_external_storage'] else 'No'}")
        self.stdout.write(f"STORAGE_BACKEND: {diagnostico['storage_backend']}")
        self.stdout.write(f"Bucket configurado: {'Si' if diagnostico['bucket_configurado'] else 'No'}")
        self.stdout.write(f"Endpoint configurado: {'Si' if diagnostico['endpoint_configurado'] else 'No'}")
        self.stdout.write(f"Region configurada: {'Si' if diagnostico['region_configurada'] else 'No'}")
        self.stdout.write(f"Access key configurada: {'Si' if diagnostico['access_key_configurada'] else 'No'}")
        self.stdout.write(f"Secret configurada: {'Si' if diagnostico['secret_configurada'] else 'No'}")
        self.stdout.write(f"Custom domain configurado: {'Si' if diagnostico['custom_domain_configurado'] else 'No'}")
        self.stdout.write(f"Default ACL: {diagnostico['default_acl']}")
        self.stdout.write(f"Media storage activo: {diagnostico['media_storage_activo']}")
        self.stdout.write(f"MEDIA_URL: {diagnostico['media_url']}")
        for advertencia in diagnostico["advertencias"]:
            self.stdout.write(self.style.WARNING(advertencia))
