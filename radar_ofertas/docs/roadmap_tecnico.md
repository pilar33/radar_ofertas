# Roadmap tecnico

## Estado actual

- Django + SQL Server local con Docker.
- Render staging con SQLite temporal.
- Motor comercial inicial.
- OAuth Mercado Libre funcionando.
- Diagnostico Mercado Libre documentado.
- Base multifuente en preparacion.

## Etapa 3.2

- Consolidar arquitectura multifuente.
- Registrar fuentes y politicas de extraccion.
- Documentar decisiones tecnicas.
- Preparar comparacion de precios por producto canonico.
- Evitar dependencia de Mercado Libre como fuente automatica principal.

## Proximas etapas

### Conectores permitidos

Implementar conectores fuente por fuente, empezando por semaforo verde:

- CSV/Excel de proveedores.
- APIs oficiales.
- Catalogos acordados.
- Carga asistida por URL.

### Analisis comercial avanzado

- Comparacion historica de precios.
- Deteccion de fuente mas barata.
- Ranking de oportunidades multifuente.
- Segmentacion por rubro, estacionalidad y logistica.

### OpenAI bajo demanda

Agregar IA solo bajo accion del usuario para:

- Normalizacion asistida.
- Resumen de producto.
- Generacion de contenido avanzado.
- Explicacion de oportunidades.

No ejecutar IA automaticamente ni sin control de costos.
