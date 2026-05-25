# Storage externo en Render

Render usa filesystem efimero: los archivos subidos pueden perderse tras redeploy, reinicio o recreacion del servicio. Por eso las importaciones CSV/Excel deben poder guardarse en un storage externo para uso real.

## Static files vs media files

- Static files: CSS, JS, imagenes propias de la app. Se sirven con WhiteNoise y `collectstatic`.
- Media files: archivos subidos por usuarios, como importaciones CSV/Excel. Deben ir a `MEDIA_ROOT` local o a storage externo.

## Variables

```env
USE_EXTERNAL_STORAGE=True
STORAGE_BACKEND=s3
STORAGE_BUCKET_NAME=
STORAGE_ACCESS_KEY_ID=
STORAGE_SECRET_ACCESS_KEY=
STORAGE_REGION_NAME=
STORAGE_ENDPOINT_URL=
STORAGE_CUSTOM_DOMAIN=
STORAGE_DEFAULT_ACL=private
MEDIA_URL=/media/
```

El backend es compatible con S3, por lo que puede usarse con AWS S3, Cloudflare R2, Backblaze B2 compatible S3, MinIO u otro proveedor equivalente.

## Proveedor S3-compatible

### Cloudflare R2

```env
USE_EXTERNAL_STORAGE=True
STORAGE_BACKEND=s3
STORAGE_BUCKET_NAME=nombre-bucket
STORAGE_ACCESS_KEY_ID=...
STORAGE_SECRET_ACCESS_KEY=...
STORAGE_REGION_NAME=auto
STORAGE_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
STORAGE_DEFAULT_ACL=private
```

### AWS S3

```env
USE_EXTERNAL_STORAGE=True
STORAGE_BACKEND=s3
STORAGE_BUCKET_NAME=nombre-bucket
STORAGE_ACCESS_KEY_ID=...
STORAGE_SECRET_ACCESS_KEY=...
STORAGE_REGION_NAME=us-east-1
STORAGE_ENDPOINT_URL=
STORAGE_DEFAULT_ACL=private
```

### MinIO local

```env
USE_EXTERNAL_STORAGE=True
STORAGE_BACKEND=s3
STORAGE_BUCKET_NAME=radar-ofertas
STORAGE_ACCESS_KEY_ID=...
STORAGE_SECRET_ACCESS_KEY=...
STORAGE_ENDPOINT_URL=http://localhost:9000
STORAGE_REGION_NAME=us-east-1
STORAGE_DEFAULT_ACL=private
```

Codex no crea credenciales reales. Las credenciales se configuran manualmente en Render Environment Variables. El bucket debe ser privado por defecto. Los archivos importados son media files, no static files.

## Activacion

En local, dejar:

```env
USE_EXTERNAL_STORAGE=False
```

En Render, configurar:

```env
USE_EXTERNAL_STORAGE=True
```

y cargar las credenciales del proveedor en variables de entorno. No subir secretos al repositorio.

## Diagnostico

Vista:

```text
/storage/diagnostico/
```

Comandos:

```bash
python manage.py diagnosticar_storage
python manage.py probar_storage
python manage.py probar_storage --keep
```

## Pendiente para produccion

- Elegir proveedor definitivo.
- Definir politica de retencion de archivos importados.
- Definir si los archivos deben ser privados siempre o si se usaran URLs firmadas.
- Agregar limpieza de archivos viejos si el volumen crece.
