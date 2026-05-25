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

## Etapa 3.1 - Configuracion Mercado Libre, OAuth y manejo de 403

Si Mercado Libre devuelve `403 Forbidden`, el sistema registra el error en `ConsultaMercadoLibre`, no se cae y muestra diagnostico para decidir si hace falta token.

### Crear app en Mercado Libre Developers

1. Entrar al portal de desarrolladores de Mercado Libre.
2. Crear una aplicacion.
3. Configurar Redirect URI igual a:

```text
http://localhost:8000/mercadolibre/oauth/callback/
```

4. Copiar Client ID y Client Secret al archivo `.env`.

### Variables `.env`

```env
MELI_BASE_URL=https://api.mercadolibre.com
MELI_AUTH_BASE_URL=https://auth.mercadolibre.com.ar
MELI_SITE_ID=MLA
MELI_CLIENT_ID=
MELI_CLIENT_SECRET=
MELI_REDIRECT_URI=http://localhost:8000/mercadolibre/oauth/callback/
MELI_ACCESS_TOKEN=
MELI_REFRESH_TOKEN=
MELI_SEARCH_LIMIT_DEFAULT=20
MELI_REQUEST_TIMEOUT=15
MELI_USER_AGENT=radar_ofertas/1.0
MELI_AFFILIATE_TAG=
MELI_AFFILIATE_BASE_URL=
```

`MELI_ACCESS_TOKEN` es opcional. Si existe, se usa como `Authorization: Bearer`. Si no existe, se intenta busqueda publica con headers completos.

### Diagnostico

```bash
docker compose exec web python manage.py diagnosticar_meli
```

El diagnostico muestra si hay Client ID, Client Secret, token activo y Redirect URI configurados sin imprimir secretos completos.

### Probar busqueda

```bash
docker compose exec web python manage.py buscar_meli --query "organizador cocina" --limit 10
```

### Autorizar desde navegador

- http://localhost:8000/mercadolibre/oauth/iniciar/
- http://localhost:8000/mercadolibre/oauth/diagnostico/
- http://localhost:8000/mercadolibre/buscar/

### Sobre el error 403

Puede ocurrir si:

- El endpoint requiere token desde este entorno.
- Mercado Libre aplica restricciones temporales o por origen.
- El token esta vencido, invalido o sin permisos suficientes.
- Los headers no son aceptados por el endpoint.

El sistema ahora guarda `status_code`, `requiere_token`, `forbidden` y `uso_token` en cada consulta.

### Link afiliado

El sistema deja preparado `url_afiliado`, `afiliado_activo` y `nota_afiliado` en `Producto`.

Por ahora el link afiliado puede cargarse manualmente desde admin. No se asume un formato automatico si Mercado Libre no lo confirma, no se publican links automaticamente y no se modifica la URL original.

## Diagnostico de 403 con token

Si OAuth genera token pero `/sites/MLA/search` sigue devolviendo `403 Forbidden`, usar el diagnostico de endpoints:

```bash
python manage.py diagnosticar_meli_endpoints --query "calza mujer" --item-id MLA3092462776 --limit 1
```

En Render normalmente no hay shell persistente disponible, asi que se puede usar la vista web:

```text
https://radar-ofertas.onrender.com/mercadolibre/diagnostico-endpoints/
```

La vista prueba:

- `/users/me` con token, para validar OAuth.
- `/sites/MLA/categories`, endpoint publico simple.
- `/sites/MLA/search` sin token.
- `/sites/MLA/search` con token.
- `/items/{item_id}` con token.

Si `/users/me` funciona pero `/sites/MLA/search` falla con `403`, el problema no es OAuth ni Redirect URI: Mercado Libre esta restringiendo el endpoint de busqueda general para esa app, token, scopes o tipo de cuenta.

Si se confirma restriccion de `/sites/MLA/search`, no se debe usar scraping. Alternativas limpias:

- Usar el sistema para analizar productos pegados manualmente por URL.
- Usar links obtenidos desde el programa de afiliados o carga manual.
- Analizar productos cargados manualmente desde admin o formularios internos.
- Evaluar acceso partner/oficial si Mercado Libre lo requiere.
- Mantener Mercado Libre API solo para endpoints permitidos por la app.

## Despliegue staging en Render para OAuth Mercado Libre

Render permite tener una URL publica HTTPS para validar OAuth de Mercado Libre. Esta configuracion usa SQLite solo como staging, sin cambiar la base empresarial local con SQL Server.

### Variables sugeridas en Render

```env
RENDER=True
USE_SQLITE_FOR_RENDER=True
DEBUG=False
SECRET_KEY=generar-una-clave-segura
ALLOWED_HOSTS=radar-ofertas.onrender.com,.onrender.com
CSRF_TRUSTED_ORIGINS=https://radar-ofertas.onrender.com
SQLITE_PATH=/opt/render/project/src/db.sqlite3

MELI_BASE_URL=https://api.mercadolibre.com
MELI_AUTH_BASE_URL=https://auth.mercadolibre.com.ar
MELI_SITE_ID=MLA
MELI_CLIENT_ID=
MELI_CLIENT_SECRET=
MELI_REDIRECT_URI=https://radar-ofertas.onrender.com/mercadolibre/oauth/callback/
MELI_USER_AGENT=radar_ofertas/1.0
```

No subir secrets al repositorio. Configurar `SECRET_KEY`, `MELI_CLIENT_ID` y `MELI_CLIENT_SECRET` solo como variables de entorno en Render.

### Start command

```bash
bash render_start.sh
```

El script ejecuta:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000}
```

### Health check

```text
https://radar-ofertas.onrender.com/health/
```

Respuesta esperada:

```json
{"status": "ok", "app": "radar_ofertas"}
```

### Redirect URI para Mercado Libre Developers

Configurar exactamente:

```text
https://radar-ofertas.onrender.com/mercadolibre/oauth/callback/
```

### Notas

- La version Render usa SQLite solo para validar OAuth/staging.
- El entorno local sigue funcionando con Docker + SQL Server + `mssql-django`.
- Para produccion real se debe definir una base externa persistente.
- No se usa OpenAI, no se usa scraping y no se automatizan compras ni publicaciones.
