import os
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from oportunidades.management.commands.preparar_decohome import preparar_decohome
from oportunidades.models import ConfiguracionExtractorWeb


def configurar_extractor_decohome():
    fuente, conector = preparar_decohome()
    url_base = os.getenv("DECOHOME_URL_BASE", fuente.url_base)
    dominio = urlparse(url_base).netloc
    config, creado = ConfiguracionExtractorWeb.objects.update_or_create(
        conector=conector,
        defaults={
            "url_inicio": url_base,
            "url_categoria": "",
            "dominio_permitido": dominio,
            "modo_extraccion": ConfiguracionExtractorWeb.MODO_PREVIEW_MANUAL,
            "max_paginas": 1,
            "max_productos": 10,
            "delay_segundos": 2,
            "timeout_segundos": 15,
            "habilitado": False,
            "solo_preview": True,
            "observaciones": "Configuracion inicial. No habilitar hasta revisar terminos, robots y selectores.",
        },
    )
    return config, creado


class Command(BaseCommand):
    help = "Configura extractor web inicial para Deco Home sin activarlo."

    def handle(self, *args, **options):
        config, creado = configurar_extractor_decohome()
        if not config.dominio_permitido:
            raise CommandError("No se pudo determinar dominio permitido.")
        self.stdout.write(self.style.SUCCESS("Extractor Deco Home configurado."))
        self.stdout.write(f"Extractor ID: {config.pk}")
        self.stdout.write(f"Creado: {'Si' if creado else 'No'}")
        self.stdout.write("Habilitado: No")
        self.stdout.write("Solo preview: Si")
