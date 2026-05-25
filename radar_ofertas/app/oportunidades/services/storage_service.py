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
    region = getattr(settings, "AWS_S3_REGION_NAME", "") if use_external else ""
    custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "") if use_external else ""
    default_acl = getattr(settings, "AWS_DEFAULT_ACL", "private") if use_external else "local"
    backend = getattr(settings, "STORAGE_BACKEND", "local" if not use_external else "s3")
    media_storage_activo = "s3" if use_external and backend == "s3" else "local"

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
        if not endpoint and not region:
            faltantes.append("STORAGE_ENDPOINT_URL o STORAGE_REGION_NAME")
        if faltantes:
            advertencias.append("Faltan variables criticas de storage externo: " + ", ".join(faltantes))

    return {
        "render": render,
        "use_external_storage": use_external,
        "storage_backend": backend,
        "bucket_configurado": bool(bucket),
        "endpoint_configurado": bool(endpoint),
        "region_configurada": bool(region),
        "access_key_configurada": bool(access_key),
        "secret_configurada": bool(secret_key),
        "custom_domain_configurado": bool(custom_domain),
        "default_acl": default_acl,
        "media_storage_activo": media_storage_activo,
        "media_url": settings.MEDIA_URL,
        "advertencias": advertencias,
    }


def probar_storage(keep=False):
    nombre = f"diagnostico_storage/radar_ofertas_test.txt"
    contenido = b"radar_ofertas storage ok"
    try:
        if default_storage.exists(nombre):
            default_storage.delete(nombre)
        guardado = default_storage.save(nombre, ContentFile(contenido))
        if not default_storage.exists(guardado):
            return {"ok": False, "mensaje": "El archivo no aparece como existente despues de guardarse.", "path": guardado}
        leido = default_storage.open(guardado, "rb").read()
        if leido != contenido:
            return {"ok": False, "mensaje": "El archivo se guardo, pero el contenido leido no coincide."}
        if not keep and default_storage.exists(guardado):
            default_storage.delete(guardado)
        if keep:
            return {"ok": True, "mensaje": "Storage OK: archivo conservado para revision manual.", "path": guardado}
        return {"ok": True, "mensaje": "Storage OK: escritura, lectura y eliminacion funcionaron.", "path": guardado}
    except Exception as exc:
        return {"ok": False, "mensaje": f"Error de storage: {exc}", "path": None}
