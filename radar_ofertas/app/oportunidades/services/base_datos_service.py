from django.conf import settings
from django.db import connection

from oportunidades.models import (
    CandidatoCompra,
    FuenteWeb,
    PrecioFuente,
    ProductoCanonico,
    ProductoFuente,
    ResultadoExtraccionWeb,
    ResultadoLaboratorioMapeo,
)
from oportunidades.services.entorno_service import es_render


def _bool_texto(valor):
    return "Si" if valor else "No"


def _contar_seguro(modelo):
    try:
        return modelo.objects.count()
    except Exception:
        return None


def obtener_diagnostico_base_datos():
    db_config = settings.DATABASES.get("default", {})
    engine = db_config.get("ENGINE", "")
    vendor = connection.vendor
    is_sqlite = "sqlite" in engine or vendor == "sqlite"
    is_sqlserver = engine == "mssql" or vendor == "microsoft"
    render = es_render()
    persistente = is_sqlserver or not (render and is_sqlite)

    advertencia = ""
    recomendacion = "SQL Server local con Docker es la base principal de trabajo."
    if render and is_sqlite:
        advertencia = (
            "Este entorno usa SQLite en Render. Sirve para staging/demo, pero los datos "
            "pueden perderse tras redeploy si no hay base persistente externa."
        )
        recomendacion = (
            "Usar Render solo para pruebas. Para datos reales, migrar a PostgreSQL, SQL Server externo "
            "u otra base persistente antes de cargar informacion valiosa."
        )
    elif is_sqlite:
        advertencia = "El entorno actual usa SQLite. Verificar que sea intencional para pruebas locales."
    elif not is_sqlserver:
        advertencia = "El motor actual no es SQL Server. Revisar variables de entorno si no era esperado."

    conteos = {
        "FuenteWeb": _contar_seguro(FuenteWeb),
        "ProductoCanonico": _contar_seguro(ProductoCanonico),
        "ProductoFuente": _contar_seguro(ProductoFuente),
        "PrecioFuente": _contar_seguro(PrecioFuente),
        "ResultadoLaboratorioMapeo": _contar_seguro(ResultadoLaboratorioMapeo),
        "ResultadoExtraccionWeb": _contar_seguro(ResultadoExtraccionWeb),
        "CandidatoCompra": _contar_seguro(CandidatoCompra),
    }

    return {
        "engine": engine,
        "vendor": vendor,
        "name": str(db_config.get("NAME", "")),
        "host": db_config.get("HOST", ""),
        "port": db_config.get("PORT", ""),
        "is_sqlite": is_sqlite,
        "is_sqlserver": is_sqlserver,
        "render": render,
        "persistente": persistente,
        "advertencia": advertencia,
        "recomendacion": recomendacion,
        "conteos": conteos,
        "resumen": {
            "SQLite": _bool_texto(is_sqlite),
            "SQL Server": _bool_texto(is_sqlserver),
            "Render": _bool_texto(render),
            "Persistente": _bool_texto(persistente),
        },
    }
