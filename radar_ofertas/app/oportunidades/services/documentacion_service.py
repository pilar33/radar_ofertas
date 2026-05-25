from oportunidades.models import DecisionTecnica


def registrar_decision_tecnica(titulo, descripcion, categoria, decision="", motivo="", impacto=""):
    decision_tecnica, _ = DecisionTecnica.objects.update_or_create(
        titulo=titulo,
        defaults={
            "categoria": categoria,
            "descripcion": descripcion,
            "decision": decision,
            "motivo": motivo,
            "impacto": impacto,
        },
    )
    return decision_tecnica


def registrar_evento_integracion(fuente, resultado, observacion):
    return registrar_decision_tecnica(
        titulo=f"Evento de integracion: {fuente}",
        categoria=DecisionTecnica.CATEGORIA_INTEGRACION,
        descripcion=str(resultado),
        decision="Registrar evento para trazabilidad tecnica.",
        motivo=observacion,
        impacto="Permite auditar integraciones y decisiones futuras.",
    )
