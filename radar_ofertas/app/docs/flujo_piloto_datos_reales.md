# Flujo piloto datos reales

Usar SQL Server local para cargar dataset real. Render con SQLite queda solo como demo/staging.

Si el diagnostico indica SQLite, no cargar dataset real.

Comandos:

```bash
docker compose exec web python manage.py diagnosticar_base_datos
docker compose exec web python manage.py flujo_piloto_fuente --fuente "Ganga Home" --limite 20
docker compose exec web python manage.py validar_dataset_piloto
```

Vista:

```text
/dataset/validacion-piloto/
```
