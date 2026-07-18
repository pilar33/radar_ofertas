# Rankings de senales de venta

Esta seccion guarda rankings fechados de productos con senales fuertes de venta o demanda. No afirma unidades vendidas salvo que la fuente las informe.

## Flujo

1. Ir a `/rankings/importar/`.
2. Completar nombre, tipo, alcance, fecha, origen y estado inicial.
3. Pegar una tabla Markdown o CSV.
4. Presionar `Previsualizar`.
5. Revisar filas validas, errores, categoria normalizada, tienda, evidencia y coincidencias con productos existentes.
6. Confirmar para crear un `LoteRanking`.

El lote anterior no se sobrescribe. Al confirmar un segundo lote publicado del mismo tipo, alcance y categoria, se calculan tendencias por item.

## Pantallas

- `/rankings/`: lotes de rankings.
- `/rankings/supermercado/`: supermercado y mercaderia revendible.
- `/rankings/importar/`: importador con vista previa.
- `/rankings/lotes/<id>/`: detalle del lote.

## API

- `/api/rankings/lotes/`
- `/api/rankings/lotes/<id>/items/`
- `/api/rankings/items/`
- `/api/rankings/actual/?tipo=alta_venta&alcance=herramientas`
- `/api/rankings/items/<id>/historico/`

## Supermercado y bebidas

Los items pueden guardar presentacion individual, pack, fardo, bulto o promocion. Se calculan:

- unidades totales;
- contenido total;
- costo final puesto en Salta;
- precio por unidad;
- precio por litro;
- precio por kilogramo;
- precio por 100 ml o 100 g.

Las promociones soportadas son 2x1, 3x2, segunda unidad con descuento, descuento directo, descuento bancario, transferencia, tarjeta y personalizada.

## Fuentes candidatas

Para preparar fuentes sin activar scraping:

```powershell
docker compose exec web python manage.py preparar_fuentes_supermercado
```

Quedan con politica pendiente de revision. No se habilitan extractores automaticamente.
