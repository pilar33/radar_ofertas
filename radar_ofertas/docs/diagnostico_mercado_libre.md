# Diagnostico de integracion con Mercado Libre

Fecha aproximada del diagnostico: mayo de 2026.

URL staging usada:

```text
https://radar-ofertas.onrender.com/
```

Redirect URI:

```text
https://radar-ofertas.onrender.com/mercadolibre/oauth/callback/
```

## Estado OAuth

- Client ID configurado: si.
- Client Secret configurado: si.
- Token OAuth generado: si.
- `/users/me`: 200 OK.

## Endpoints bloqueados

- `/sites/MLA/categories`: 403.
- `/sites/MLA/search`: 403.
- `/items/{id}`: 403.

Error informado por Mercado Libre:

```text
PA_UNAUTHORIZED_RESULT_FROM_POLICIES
blocked_by: PolicyAgent
```

## Interpretacion

OAuth y token funcionan. El problema no esta en Django ni en Render.

Mercado Libre restringe los endpoints de catalogo, busqueda y productos para esta app/token. El bloqueo ocurre del lado de Mercado Libre por politicas/restricciones de acceso.

## Decision tecnica

Mercado Libre no sera fuente principal automatica en esta etapa.

Queda como fuente limitada, opcional o de analisis por URL/afiliados si corresponde. La arquitectura evoluciona hacia un radar multifuente con fuentes permitidas, datos propios, CSV/Excel, carga por URL y conectores especificos.

## Alternativas

- API oficial si se habilita en el futuro.
- Programa de afiliados si provee links o herramientas compatibles.
- Carga por URL.
- Carga por CSV/Excel.
- Uso de otras fuentes web permitidas.
- Catalogos mayoristas.
- Conectores propios solo donde sea permitido.
