# Modelo de datos multifuente

La primera version del radar usa `Producto`, `PrecioProducto` y `Oportunidad`. Estos modelos se mantienen por compatibilidad.

La evolucion multifuente agrega una capa normalizada:

- `FuenteWeb`: fuente comercial o tecnica de productos.
- `PoliticaExtraccionFuente`: semaforo, metodo permitido y riesgos.
- `CategoriaFuente`: categorias propias de cada fuente, mapeables a `CategoriaInteres`.
- `ProductoCanonico`: producto normalizado independiente de la fuente.
- `ProductoFuente`: aparicion de un producto en una fuente especifica.
- `PrecioFuente`: historial de precios por fuente.
- `ComparacionPrecio`: agregados de precio por producto canonico.
- `EvaluacionOportunidadMultifuente`: evaluacion comercial usando precios y fuentes.
- `DecisionTecnica`: registro de decisiones relevantes.

## Compatibilidad

No se eliminan modelos existentes. En futuras etapas se podra migrar gradualmente:

```text
Producto -> ProductoFuente / ProductoCanonico
PrecioProducto -> PrecioFuente
Oportunidad -> EvaluacionOportunidadMultifuente
```

La migracion debe ser gradual y reversible, evitando perdida de datos.

## Uso futuro

Este modelo permite:

- Comparar precios entre fuentes.
- Registrar historiales por proveedor.
- Separar producto real de publicacion/listado.
- Evaluar politicas de extraccion antes de automatizar.
- Preparar dataset propio para analisis e IA bajo demanda.
