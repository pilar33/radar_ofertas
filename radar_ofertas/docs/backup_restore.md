# Backup y restore

El sistema permite exportar un snapshot JSON de los datos clave.

Comandos:

```bash
docker compose exec web python manage.py exportar_snapshot --output data/backups/snapshot_radar.json
docker compose exec web python manage.py importar_snapshot --input data/backups/snapshot_radar.json --dry-run
docker compose exec web python manage.py importar_snapshot --input data/backups/snapshot_radar.json
```

La importacion web queda deshabilitada por seguridad. Usar comandos para evitar operaciones accidentales.
