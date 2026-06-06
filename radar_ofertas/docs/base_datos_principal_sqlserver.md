# Base principal SQL Server

SQL Server local con Docker es la base principal actual del proyecto `radar_ofertas`.

Render puede seguir usando SQLite temporal para staging/demo, pero no debe tratarse como almacenamiento persistente de datos reales.

## Entorno local

Levantar servicios:

```bash
docker compose up -d
```

Ejecutar migraciones:

```bash
docker compose exec web python manage.py migrate
```

Diagnosticar la base activa:

```bash
docker compose exec web python manage.py diagnosticar_base_datos
```

## Backups y exports

Snapshot JSON:

```bash
docker compose exec web python manage.py exportar_snapshot --output data/backups/snapshot_radar.json
```

Validar importacion sin escribir:

```bash
docker compose exec web python manage.py importar_snapshot --input data/backups/snapshot_radar.json --dry-run
```

Dataset completo:

```bash
docker compose exec web python manage.py exportar_dataset_completo --output data/exports/radar_dataset.zip
```

Backup rapido:

```bash
docker compose exec web python manage.py backup_rapido_dataset
```

## Cuidado con el volumen Docker

El volumen `sqlserver_data` conserva la base local de SQL Server.

No ejecutar:

```bash
docker compose down -v
```

si se quieren conservar datos. Ese comando elimina volumenes y puede borrar la base local.

## Render

La configuracion staging en Render puede usar:

```env
RENDER=True
USE_SQLITE_FOR_RENDER=True
```

Eso sirve para validar pantallas, OAuth y flujos de prueba, pero los datos pueden perderse tras redeploy. Para uso real se debera migrar Render a PostgreSQL, SQL Server externo u otra base persistente.

## Seguridad

No subir `.env` ni secretos al repositorio. El diagnostico de base no imprime passwords, tokens ni claves.
