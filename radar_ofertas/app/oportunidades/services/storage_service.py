from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def diagnosticar_storage_config():
    use_external = bool(getattr(settings, "USE_EXTERNAL_STORAGE", False))
    render = bool(getattr(settings, "RENDER", False))
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "") if use_external else ""
    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "") if use_external else ""
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "") if use_external else ""
    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", "") if use_external else ""
    backend = getattr(settings, "STORAGE_BACKEND", "local" if not use_external else "s3")

    advertencias = []
    if render and not use_external:
        advertencias.append(
            "Render usa filesystem efimero. Los archivos subidos pueden perderse tras redeploy. "
            "Configurar storage externo para uso real."
        )
    if use_external:
        faltantes = []
        if not bucket:
            faltantes.append("STORAGE_BUCKET_NAME")
        if not access_key:
            faltantes.append("STORAGE_ACCESS_KEY_ID")
        if not secret_key:
            faltantes.append("STORAGE_SECRET_ACCESS_KEY")
        if faltantes:
            advertencias.append("Faltan variables criticas de storage externo: " + ", ".join(faltantes))

    return {
        "render": render,
        "use_external_storage": use_external,
        "storage_backend": backend,
        "bucket_configurado": bool(bucket),
        "endpoint_configurado": bool(endpoint),
        "access_key_configurada": bool(access_key),
        "secret_configurada": bool(secret_key),
        "media_url": settings.MEDIA_URL,
        "advertencias": advertencias,
    }


def probar_storage():
    nombre = "diagnostico_storage/radar_ofertas_test.txt"
    contenido = b"radar_ofertas storage ok"
    try:
        if default_storage.exists(nombre):
            default_storage.delete(nombre)
        guardado = default_storage.save(nombre, ContentFile(contenido))
        leido = default_storage.open(guardado, "rb").read()
        if leido != contenido:
            return {"ok": False, "mensaje": "El archivo se guardo, pero el contenido leido no coincide."}
        if default_storage.exists(guardado):
            default_storage.delete(guardado)
        return {"ok": True, "mensaje": "Storage OK: escritura, lectura y eliminacion funcionaron."}
    except Exception as exc:
        return {"ok": False, "mensaje": f"Error de storage: {exc}"}
