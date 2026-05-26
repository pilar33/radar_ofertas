from django.utils import timezone

from oportunidades.models import PoliticaExtraccionFuente, RevisionManualFuente


def aplicar_revision_a_politica(revision):
    politica, _ = PoliticaExtraccionFuente.objects.get_or_create(fuente=revision.fuente_web)

    if revision.tipo_revision == RevisionManualFuente.TIPO_TERMINOS:
        politica.terminos_revisados = True
    if revision.tipo_revision == RevisionManualFuente.TIPO_ROBOTS:
        politica.robots_txt_revisado = True

    if revision.resultado == RevisionManualFuente.RESULTADO_PROHIBE:
        politica.semaforo = PoliticaExtraccionFuente.SEMAFORO_ROJO
        politica.permite_scraping = False
        politica.metodo_preferido = PoliticaExtraccionFuente.METODO_NO_PERMITIDO
    elif revision.resultado == RevisionManualFuente.RESULTADO_DUDOSO:
        if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_VERDE:
            politica.semaforo = PoliticaExtraccionFuente.SEMAFORO_AMARILLO
        elif politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO:
            politica.semaforo = PoliticaExtraccionFuente.SEMAFORO_AMARILLO
        politica.permite_scraping = False
    elif revision.resultado == RevisionManualFuente.RESULTADO_PERMITE:
        decision = (revision.decision or "").lower()
        if "verde" in decision:
            politica.semaforo = PoliticaExtraccionFuente.SEMAFORO_VERDE
        elif politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO:
            politica.semaforo = PoliticaExtraccionFuente.SEMAFORO_AMARILLO
        if "permite scraping" in decision or "scraping permitido" in decision:
            politica.permite_scraping = True

    politica.fecha_revision = timezone.now()
    politica.observaciones = "\n".join(
        filter(
            None,
            [
                politica.observaciones,
                f"Revision manual {revision.tipo_revision}: {revision.resultado}. {revision.resumen}",
            ],
        )
    )
    politica.save()
    return politica


def crear_revision_manual(datos, aplicar=False):
    revision = RevisionManualFuente.objects.create(**datos, aplicar_a_politica=aplicar)
    politica = aplicar_revision_a_politica(revision) if aplicar else None
    return revision, politica
