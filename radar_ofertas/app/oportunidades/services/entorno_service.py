import os

from django.conf import settings
from django.db import connection


def es_render():
    return os.getenv("RENDER", "False") == "True"


def usa_sqlite():
    engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
    return "sqlite" in engine or connection.vendor == "sqlite"


def entorno_no_persistente():
    return es_render() and usa_sqlite()


def obtener_advertencia_persistencia():
    if not entorno_no_persistente():
        return ""
    return (
        "Este entorno usa SQLite en Render. Los datos pueden perderse en redeploy. "
        "Usar solo para pruebas/staging. La base principal de trabajo debe ser SQL Server local "
        "o una base cloud persistente."
    )
