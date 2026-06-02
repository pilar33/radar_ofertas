# Persistencia de datos

El entorno local con SQL Server en Docker sigue siendo la base principal de trabajo.

Render usa SQLite temporalmente como staging/demo. Ese filesystem puede perder datos en redeploy, recreacion del servicio o cambios de infraestructura. No conviene cargar datos valiosos ahi sin exportar antes.

Recomendaciones:

- Usar Render + SQLite solo para pruebas funcionales.
- Exportar dataset o snapshot antes de redeploys importantes.
- Mantener SQL Server local como fuente principal mientras no exista base cloud persistente.
- Migrar mas adelante a una base persistente como Render PostgreSQL, Azure SQL, SQL Server externo, Supabase/PostgreSQL, Railway u otro proveedor.

No se migra automaticamente en esta etapa.
