from django.core.management.base import BaseCommand

from oportunidades.services.mercado_libre_service import buscar_productos, get_meli_config, obtener_token_activo


class Command(BaseCommand):
    help = "Diagnostica configuracion, headers y acceso a la API de Mercado Libre."

    def handle(self, *args, **options):
        config = get_meli_config()
        token = obtener_token_activo()

        self.stdout.write("Configuracion Mercado Libre")
        self.stdout.write(f"MELI_BASE_URL: {config['base_url']}")
        self.stdout.write(f"MELI_SITE_ID: {config['site_id']}")
        self.stdout.write(f"MELI_CLIENT_ID configurado: {'si' if bool(config['client_id']) else 'no'}")
        self.stdout.write(f"MELI_CLIENT_SECRET configurado: {'si' if bool(config['client_secret']) else 'no'}")
        self.stdout.write(f"MELI_ACCESS_TOKEN configurado: {'si' if bool(config['access_token']) else 'no'}")
        self.stdout.write(f"Token activo disponible: {'si' if bool(token) else 'no'}")
        self.stdout.write(f"MELI_REDIRECT_URI: {config['redirect_uri']}")

        self.stdout.write("")
        self.stdout.write("Prueba sin token")
        sin_token = buscar_productos("organizador cocina", limit=1, usar_token_si_existe=False)
        self.stdout.write(f"status_code: {sin_token.get('status_code')}")
        self.stdout.write(f"ok: {sin_token.get('ok')}")
        self.stdout.write(f"error: {sin_token.get('error')}")

        con_token = None
        if token:
            self.stdout.write("")
            self.stdout.write("Prueba con token")
            con_token = buscar_productos("organizador cocina", limit=1, usar_token_si_existe=True)
            self.stdout.write(f"status_code: {con_token.get('status_code')}")
            self.stdout.write(f"ok: {con_token.get('ok')}")
            self.stdout.write(f"error: {con_token.get('error')}")

        self.stdout.write("")
        self.stdout.write("Diagnostico")
        if sin_token.get("ok"):
            self.stdout.write(self.style.SUCCESS("La busqueda publica funciona sin token."))
        elif sin_token.get("forbidden") and con_token and con_token.get("ok"):
            self.stdout.write(self.style.WARNING("La API requiere token para esta consulta desde este entorno."))
        elif sin_token.get("forbidden") and con_token and con_token.get("forbidden"):
            self.stdout.write(
                self.style.ERROR("Revisar permisos de la app, token, headers, endpoint o restricciones de Mercado Libre.")
            )
        elif not token:
            self.stdout.write(
                self.style.WARNING(
                    "MELI_ACCESS_TOKEN no configurado. Se puede crear app y obtener token OAuth si el endpoint lo requiere."
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Revisar el detalle de errores anterior."))
