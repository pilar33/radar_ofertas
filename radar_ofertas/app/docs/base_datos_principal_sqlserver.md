# Base principal SQL Server

SQL Server local con Docker es la base principal actual. Render con SQLite queda como staging/demo temporal.

Comandos utiles:

```bash
docker compose exec web python manage.py diagnosticar_base_datos
docker compose exec web python manage.py backup_rapido_dataset
docker compose exec web python manage.py exportar_snapshot --output data/backups/snapshot_radar.json
docker compose exec web python manage.py exportar_dataset_completo --output data/exports/radar_dataset.zip
```

No ejecutar `docker compose down -v` si se quieren conservar datos del volumen `sqlserver_data`.
