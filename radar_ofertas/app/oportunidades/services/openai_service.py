import os


def analizar_con_ia(oportunidad_id):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return {
            "oportunidad_id": oportunidad_id,
            "estado": "pendiente",
            "mensaje": "OPENAI_API_KEY no configurada. Integracion pendiente.",
        }

    raise NotImplementedError("Integracion con OpenAI pendiente para una etapa posterior.")
