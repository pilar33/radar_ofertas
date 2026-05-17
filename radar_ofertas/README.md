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
- `POST /api/oportunidades/<id>/recalcular/`
- `POST /api/oportunidades/<id>/generar-contenido/`
- `GET /api/meli/buscar/?q=organizador&limit=10`
- `POST /api/meli/sincronizar/`
- `GET /api/meli/consultas/`

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

## Etapa 2 - Motor comercial

Esta etapa mejora los servicios comerciales internos para calcular precios, margen, porcentaje de margen, riesgo, puntaje, clasificacion de oportunidad y contenido sugerido basico sin usar APIs externas.

Comandos utiles:

```bash
docker compose exec web python manage.py recalcular_oportunidades
docker compose exec web python manage.py generar_contenidos_basicos
docker compose exec web python manage.py test oportunidades
```

Tambien se agregan acciones web y API para recalcular una oportunidad individual y generar contenido basico sin IA.

## Etapa 3 - Integracion Mercado Libre API publica

Esta etapa consume la API publica/oficial de Mercado Libre Argentina para buscar productos, guardarlos en SQL Server, registrar historial de precios y generar oportunidades con el motor comercial existente.

Variables nuevas:

```env
MELI_BASE_URL=https://api.mercadolibre.com
MELI_SITE_ID=MLA
MELI_SEARCH_LIMIT_DEFAULT=20
MELI_REQUEST_TIMEOUT=15
MELI_ACCESS_TOKEN=
```

`MELI_ACCESS_TOKEN` es opcional. Para busquedas publicas iniciales se puede dejar vacio; si se configura, se envia como `Bearer Token`.

Comandos:

```bash
docker compose exec web python manage.py buscar_meli --query "organizador cocina" --limit 10
docker compose exec web python manage.py buscar_meli --categoria-id 1 --limit 20
docker compose exec web python manage.py buscar_meli_categorias --limit 10 --delay 2
```

URLs:

- http://localhost:8000/mercadolibre/buscar/
- http://localhost:8000/oportunidades/

Aclaraciones:

- No se usa scraping.
- No se usa OpenAI en esta etapa.
- No se automatizan compras.
- No se publican productos automaticamente.
- Las consultas se registran en `ConsultaMercadoLibre`.
- Se evita duplicar productos por fuente y codigo externo.
- Se evita duplicar precios cuando el precio no cambio.
- Usar limites moderados y delay entre consultas para respetar un uso prudente de la API.
