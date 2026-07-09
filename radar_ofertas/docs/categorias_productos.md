# Categorias de productos

Radar guarda dos niveles de categoria:

- `categoria_original`: texto capturado desde la tienda, marketplace, CSV o carga asistida. No se normaliza ni reemplaza, porque sirve para auditar de donde vino el dato.
- `categoria_normalizada`: categoria estandar del Radar. En el modelo actual se representa con `CategoriaInteres` y se usa desde `ProductoCanonico.categoria`.

En productos por fuente (`ProductoFuente`) tambien se guardan `subcategoria_original` y `etiquetas` para conservar detalles utiles como marca, linea, uso o palabras clave.

## Categorias base

La migracion `0023_categorias_base_normalizadas` carga estas categorias si no existen:

- Materiales de obra
- Herramientas
- Electrodomesticos
- Hogar
- Vestimenta
- Calzado
- Ropa de trabajo
- Tecnologia
- Muebles
- Jardin
- Otros

No duplica categorias: busca primero por `slug` y despues por nombre.

## Clasificacion automatica

El servicio `oportunidades.services.categorias_service.clasificar_categoria_producto` propone una categoria usando:

- titulo del producto;
- categoria original;
- descripcion;
- marca;
- nombre y rubro de la fuente.

Las reglas iniciales cubren terminos como `taladro`, `amoladora`, `cemento`, `heladera`, `pampero`, `bambu`, `botin`, `silla`, `jardin`, etc. Si no encuentra una coincidencia clara, asigna `Otros`.

La clasificacion inicial no bloquea la creacion del producto. Luego se puede corregir manualmente editando el `ProductoCanonico.categoria` desde Django Admin o desde futuras pantallas de curaduria.

## Agregar o ajustar categorias

Para agregar una categoria:

1. Crear o editar una `CategoriaInteres` desde Django Admin.
2. Completar `nombre`, `slug`, `palabra_clave`, `prioridad` y dejarla `activa`.
3. Usar `palabras_clave` para terminos separados por coma.
4. Usar `marcas_clave` para marcas prioritarias, por ejemplo `Pampero, Ombu, Grafa`.

Para ajustar reglas globales, editar `CATEGORIAS_BASE` o las reglas de `clasificar_categoria_producto`.

## API

Endpoints utiles:

- `/api/categorias/`
- `/api/productos/?categoria=herramientas`
- `/api/productos/?categoria_original=Herramientas`
- `/api/productos-canonicos/?categoria=calzado`
- `/api/productos-multifuente/?categoria=electrodomesticos`
- `/api/ofertas/?categoria=ropa-de-trabajo`

`categoria` acepta slug, nombre o id numerico.

## Revision de productos mal clasificados

En Django Admin:

1. Abrir `Productos por fuente`.
2. Revisar `categoria_original`, `categoria_normalizada` y `precio_actual`.
3. Si la normalizada esta mal, abrir el producto canonico asociado y cambiar su `categoria`.
4. Si la tienda informa una categoria incompleta, corregir `categoria_original`, `subcategoria_original` o `etiquetas` en `ProductoFuente`.

Esta estructura queda preparada para futuras alertas por categorias de interes: se puede reutilizar `CategoriaInteres`, `prioridad`, `palabras_clave` y `marcas_clave` como base de una futura configuracion con descuento minimo y marcas prioritarias.
