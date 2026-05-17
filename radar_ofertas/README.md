# radar_ofertas

Base tecnica para detectar y evaluar oportunidades comerciales en productos publicados en marketplaces y tiendas online.

Esta etapa crea el proyecto con Django, Django REST Framework, SQL Server y Docker. No integra APIs externas, no consume Mercado Libre, no llama a OpenAI y no usa scraping.

## 1. Requisitos

- Docker Desktop
- Docker Compose
- Python 3.11 o superior si se ejecuta fuera de Docker
- Puerto `8000` disponible para Django
- Puerto `1433` disponible para SQL Server

## 2. Crear `.env`

Copiar el archivo de ejemplo:

```bash
cp .env.example .env
```

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Editar `.env` si se desea cambiar claves, password o configuracion de base de datos. No subir `.env` al repositorio.

## 3. Levantar Docker

```bash
docker compose up --build
```

El servicio `db` usa SQL Server 2022 y el servicio `web` ejecuta Django en `http://localhost:8000/`.

## 4. Ejecutar migraciones

En otra terminal:

```bash
docker compose exec web python manage.py crear_base_datos
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

## 5. Crear superusuario

```bash
docker compose exec web python manage.py createsuperuser
```

## 6. Cargar datos de prueba

```bash
docker compose exec web python manage.py cargar_datos_prueba
```

El comando inserta fuentes, categorias, productos simulados, historial de precios, oportunidades calculadas y contenidos sugeridos basicos.

## 7. Entrar al sistema

- Web: http://localhost:8000/
- Admin: http://localhost:8000/admin/
- API oportunidades: http://localhost:8000/api/oportunidades/

## Endpoints incluidos

- `GET /api/oportunidades/`
- `GET /api/oportunidades/<id>/`
- `PATCH /api/oportunidades/<id>/estado/`

Ejemplo para cambiar estado:

```bash
curl -X PATCH http://localhost:8000/api/oportunidades/1/estado/ \
  -H "Content-Type: application/json" \
  -d '{"estado": "revisado"}'
```

## Notas de arquitectura

- Las credenciales se leen desde variables de entorno.
- Los servicios de Mercado Libre y OpenAI quedan como placeholders para etapas futuras.
- La app principal es `oportunidades`.
- SQL Server se usa desde el inicio mediante `mssql-django`, `pyodbc` y ODBC Driver 18.
