import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from oportunidades.models import ConectorFuente, ConfiguracionExtractorWeb, FuenteWeb, PoliticaExtraccionFuente
from oportunidades.services.wizard_fuentes_service import preparar_fuente_generica


def _bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "y"}


class Command(BaseCommand):
    help = "Crea/actualiza un superusuario y, opcionalmente, habilita una fuente para preview en Render."

    def handle(self, *args, **options):
        self._asegurar_superusuario()
        self._configurar_fuente_preview()

    def _asegurar_superusuario(self):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write("Bootstrap admin omitido: faltan DJANGO_SUPERUSER_USERNAME o DJANGO_SUPERUSER_PASSWORD.")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        accion = "creado" if created else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Superusuario {username} {accion}."))

    @transaction.atomic
    def _configurar_fuente_preview(self):
        nombre = os.getenv("RADAR_BOOTSTRAP_FUENTE_NOMBRE")
        if not nombre:
            self.stdout.write("Bootstrap fuente omitido: RADAR_BOOTSTRAP_FUENTE_NOMBRE no configurado.")
            return

        fuente = FuenteWeb.objects.filter(nombre__iexact=nombre).first()
        if not fuente:
            url_base = os.getenv("RADAR_BOOTSTRAP_FUENTE_URL_BASE")
            rubro = os.getenv("RADAR_BOOTSTRAP_FUENTE_RUBRO", "hogar/deco")
            tipo_fuente = os.getenv("RADAR_BOOTSTRAP_TIPO_FUENTE", FuenteWeb.TIPO_TIENDA_ONLINE)
            if not url_base:
                self.stdout.write(
                    self.style.WARNING(
                        f"Fuente no encontrada: {nombre}. Para crearla configurar RADAR_BOOTSTRAP_FUENTE_URL_BASE."
                    )
                )
                return
            fuente, _, creada, _ = preparar_fuente_generica(nombre, url_base, rubro, tipo_fuente)
            self.stdout.write(self.style.SUCCESS(f"Fuente {fuente.nombre} {'creada' if creada else 'actualizada'} por bootstrap."))

        politica, _ = PoliticaExtraccionFuente.objects.get_or_create(fuente=fuente)
        politica.semaforo = os.getenv("RADAR_BOOTSTRAP_SEMAFORO", PoliticaExtraccionFuente.SEMAFORO_AMARILLO)
        politica.metodo_preferido = PoliticaExtraccionFuente.METODO_SCRAPING_PERMITIDO
        politica.permite_scraping = _bool_env("RADAR_BOOTSTRAP_PERMITE_SCRAPING", True)
        politica.robots_txt_revisado = _bool_env("RADAR_BOOTSTRAP_ROBOTS_REVISADO", True)
        politica.terminos_revisados = _bool_env("RADAR_BOOTSTRAP_TERMINOS_REVISADOS", True)
        politica.requiere_login = _bool_env("RADAR_BOOTSTRAP_REQUIERE_LOGIN", False)
        politica.tiene_captcha = _bool_env("RADAR_BOOTSTRAP_TIENE_CAPTCHA", False)
        politica.observaciones = (politica.observaciones or "") + "\nConfiguracion aplicada por bootstrap_render."
        politica.save()

        conector = (
            fuente.conectores.filter(tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO).first()
            or fuente.conectores.create(
                nombre=f"{fuente.nombre} - Extractor bootstrap",
                tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO,
                descripcion="Conector creado por bootstrap_render para preview controlado.",
            )
        )
        conector.estado = ConectorFuente.ESTADO_ACTIVO
        conector.respeta_politica_fuente = True
        conector.requiere_revision_manual = False
        conector.save()

        extractor = getattr(conector, "configuracion_web", None)
        if extractor:
            pagina_prueba = os.getenv("RADAR_BOOTSTRAP_PAGINA_PRUEBA_URL")
            url_categoria = os.getenv("RADAR_BOOTSTRAP_URL_CATEGORIA")
            modo = os.getenv("RADAR_BOOTSTRAP_MODO_EXTRACCION")
            update_fields = ["habilitado", "solo_preview", "max_paginas", "max_productos", "delay_segundos"]
            if pagina_prueba:
                extractor.pagina_prueba_url = pagina_prueba
                update_fields.append("pagina_prueba_url")
            if url_categoria:
                extractor.url_categoria = url_categoria
                update_fields.append("url_categoria")
            if modo:
                extractor.modo_extraccion = modo
                update_fields.append("modo_extraccion")
            extractor.habilitado = True
            extractor.solo_preview = True
            extractor.max_paginas = 1
            extractor.max_productos = 10
            extractor.delay_segundos = Decimal("2.00")
            extractor.save(update_fields=update_fields)

        self.stdout.write(self.style.SUCCESS(f"Fuente {fuente.nombre} configurada para preview controlado."))
