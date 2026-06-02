import json

from django.core import serializers

from oportunidades.models import (
    ComparacionPrecio,
    EvaluacionOportunidadMultifuente,
    FuenteWeb,
    PoliticaExtraccionFuente,
    PrecioFuente,
    ProductoCanonico,
    ProductoFuente,
    ResultadoExtraccionWeb,
    ResultadoLaboratorioMapeo,
    SesionLaboratorioMapeo,
)


MODELOS_SNAPSHOT = [
    FuenteWeb,
    PoliticaExtraccionFuente,
    ProductoCanonico,
    ProductoFuente,
    PrecioFuente,
    ComparacionPrecio,
    EvaluacionOportunidadMultifuente,
    SesionLaboratorioMapeo,
    ResultadoLaboratorioMapeo,
    ResultadoExtraccionWeb,
]


def exportar_snapshot_json(output=None):
    objetos = []
    for modelo in MODELOS_SNAPSHOT:
        objetos.extend(modelo.objects.all())
    data = serializers.serialize("json", objetos)
    if output:
        output.write(data)
        return output
    return data


def importar_snapshot_json(path, dry_run=True):
    with open(path, "r", encoding="utf-8") as archivo:
        contenido = archivo.read()
    objetos = list(serializers.deserialize("json", contenido))
    resumen = {"objetos": len(objetos), "creados_o_actualizados": 0, "dry_run": dry_run}
    if dry_run:
        return resumen
    for objeto in objetos:
        objeto.save()
        resumen["creados_o_actualizados"] += 1
    return resumen


def snapshot_resumen_json():
    return json.dumps({modelo.__name__: modelo.objects.count() for modelo in MODELOS_SNAPSHOT}, indent=2)
