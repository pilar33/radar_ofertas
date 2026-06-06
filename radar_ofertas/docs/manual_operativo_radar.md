# Manual operativo preliminar

## Flujo recomendado

1. Probar una web desde `/laboratorio/mapeo-web/`.
2. Revisar productos detectados, precios e imagenes.
3. Guardar como extractor si la fuente esta habilitada por politica.
4. Ejecutar preview desde el extractor.
5. Seleccionar productos convenientes.
6. Procesar resultados seleccionados.
7. Revisar productos en `/curaduria/productos/`.
8. Corregir URL, imagen, titulo o precio reciente si hace falta.
9. Revisar duplicados en `/curaduria/duplicados/`.
10. Fusionar duplicados sin borrar historial.
11. Recalcular ranking en `/oportunidades/ranking/`.
12. Marcar candidatos de compra para seguimiento.
13. Exportar dataset o snapshot antes de redeploys importantes.

## Render con SQLite

Render con SQLite es staging/demo. Los datos pueden perderse en redeploy. Para dataset real usar SQL Server local o una base cloud persistente.

## Ganga Home y nuevas fuentes

Para Ganga Home o fuentes Tienda Nube:

- crear fuente rapida;
- auditar/revisar politica;
- usar laboratorio;
- guardar extractor;
- ejecutar preview limitado;
- procesar solo seleccionados;
- curar y exportar.

No se usa OpenAI, machine learning ni scraping masivo en esta etapa.
