from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from oportunidades.models import (
    ComercioLocal,
    EvidenciaLocal,
    FuenteWeb,
    LoteCapturaLocal,
    ObjetivoVigilanciaLocal,
    ObservacionPrecioLocal,
    UmbralPrecioLocal,
)
from oportunidades.services.categorias_service import asegurar_categorias_mercaderia_local
from oportunidades.services.oportunidades_locales_service import (
    calcular_normalizacion_local,
    confirmar_importacion_local,
    evaluar_observacion,
    previsualizar_importacion_local,
)


TABLA_LOCAL = """| Ranking | Producto | Fuente | Zona | Precio encontrado | Presentacion | Unidad normalizada | Sirve para | Estado |
|---:|---|---|---|---:|---|---|---|---|
| 1 | Menudo de pollo | Vea fisico | Salta Capital | 300 | 1 kg | $/kg | alimentacion economica / alimentacion animal informada | ALERTA FUERTE |
| 2 | Fideos segunda marca | Mayorista calle Oran | calle Oran, Salta Capital | 500 | paquete de 500 g | $/kg | compra economica / stock / alimentacion animal informada | ALERTA FUERTE |
| 3 | Arroz economico | Mayorista local | Salta Capital | precio a cargar | bolsa de 1 kg | $/kg | consumo familiar / stock | VIGILAR |
"""


class OportunidadesLocalesTests(TestCase):
    def setUp(self):
        asegurar_categorias_mercaderia_local()
        self.categoria = __import__("oportunidades.models", fromlist=["CategoriaInteres"]).CategoriaInteres.objects.get(slug="mercaderia-local-oportunidad")
        self.comercio = ComercioLocal.objects.create(nombre="Mayorista calle Oran", zona="Salta Capital", tipo_fuente=FuenteWeb.TIPO_MAYORISTA)
        hoy = timezone.localdate()
        self.umbral_fideos = UmbralPrecioLocal.objects.create(
            nombre="Fideos economicos",
            categoria=self.categoria,
            unidad_normalizada=UmbralPrecioLocal.UNIDAD_KG,
            precio_maximo_bueno=Decimal("1200.00"),
            precio_maximo_fuerte=Decimal("1000.00"),
            fecha_desde=hoy - timedelta(days=1),
            fecha_hasta=hoy + timedelta(days=30),
            segunda_marca_aceptada=True,
        )

    def _obs(self, nombre="Fideos segunda marca", precio=Decimal("500.00"), presentacion="paquete de 500 g", unidad="$/kg", **extra):
        normal = calcular_normalizacion_local(precio, presentacion, unidad_normalizada=unidad, producto=nombre, traslado=extra.pop("traslado", 0))
        obs = ObservacionPrecioLocal(
            categoria=extra.pop("categoria", self.categoria),
            comercio=self.comercio,
            nombre_original=nombre,
            zona=extra.pop("zona", "Salta Capital"),
            precio_total_encontrado=precio,
            tipo_presentacion=normal["tipo_presentacion"],
            cantidad_envases=normal["cantidad_envases"],
            contenido_por_envase=normal["contenido_por_envase"],
            unidad_medida=normal["unidad_medida"],
            unidades_totales=normal["unidades_totales"],
            contenido_total_normalizado=normal["contenido_total_normalizado"],
            precio_por_unidad=normal["precio_por_unidad"],
            precio_por_kg=normal["precio_por_kg"],
            precio_por_litro=normal["precio_por_litro"],
            precio_por_metro=normal["precio_por_metro"],
            costo_traslado_envio=normal["costo_traslado_envio"],
            costo_final_puesto_salta=normal["costo_final_puesto_salta"],
            **extra,
        )
        return evaluar_observacion(obs)

    def test_fideos_500g_a_500_es_1000_por_kg(self):
        normal = calcular_normalizacion_local(Decimal("500.00"), "paquete de 500 g", unidad_normalizada="$/kg", producto="Fideos")
        self.assertEqual(normal["precio_por_kg"], Decimal("1000.00"))

    def test_menudo_300_por_kg_es_300_por_kg(self):
        normal = calcular_normalizacion_local(Decimal("300.00"), "1 kg", unidad_normalizada="$/kg", producto="Menudo de pollo")
        self.assertEqual(normal["precio_por_kg"], Decimal("300.00"))

    def test_aceite_900ml_a_2250_es_2500_por_litro(self):
        normal = calcular_normalizacion_local(Decimal("2250.00"), "900 ml", unidad_normalizada="$/litro", producto="Aceite")
        self.assertEqual(normal["precio_por_litro"], Decimal("2500.00"))

    def test_papel_4_rollos_30m_a_3600_es_30_por_metro(self):
        normal = calcular_normalizacion_local(Decimal("3600.00"), "4 rollos de 30 metros", unidad_normalizada="$/metro", producto="Papel higienico")
        self.assertEqual(normal["precio_por_metro"], Decimal("30.00"))

    def test_fardo_con_varias_unidades(self):
        normal = calcular_normalizacion_local(Decimal("6000.00"), "fardo x 12 paquetes de 500 g", unidad_normalizada="$/kg", producto="Fideos")
        self.assertEqual(normal["contenido_total_normalizado"], Decimal("6.000"))
        self.assertEqual(normal["precio_por_kg"], Decimal("1000.00"))

    def test_costo_traslado_incorporado_al_precio_final(self):
        normal = calcular_normalizacion_local(Decimal("500.00"), "paquete de 500 g", unidad_normalizada="$/kg", producto="Fideos", traslado=Decimal("100.00"))
        self.assertEqual(normal["costo_final_puesto_salta"], Decimal("600.00"))
        self.assertEqual(normal["precio_por_kg"], Decimal("1200.00"))

    def test_umbral_bueno(self):
        obs = self._obs(precio=Decimal("550.00"))
        self.assertEqual(obs.precio_por_kg, Decimal("1100.00"))
        self.assertEqual(obs.clasificacion_automatica, ObservacionPrecioLocal.CLASIFICACION_BUENA)

    def test_umbral_fuerte(self):
        obs = self._obs()
        self.assertEqual(obs.clasificacion_automatica, ObservacionPrecioLocal.CLASIFICACION_ALERTA_FUERTE)

    def test_umbral_vencido_no_aplica(self):
        self.umbral_fideos.fecha_hasta = timezone.localdate() - timedelta(days=1)
        self.umbral_fideos.save()
        obs = self._obs()
        self.assertEqual(obs.clasificacion_automatica, ObservacionPrecioLocal.CLASIFICACION_REVISAR)

    def test_segunda_marca_aceptada(self):
        obs = self._obs(segunda_marca=True)
        self.assertEqual(obs.clasificacion_automatica, ObservacionPrecioLocal.CLASIFICACION_ALERTA_FUERTE)

    def test_marca_obligatoria_no_compara_marca_distinta(self):
        self.umbral_fideos.marca = "Marca A"
        self.umbral_fideos.marca_importa = True
        self.umbral_fideos.save()
        obs = self._obs(marca="Marca B")
        self.assertEqual(obs.clasificacion_automatica, ObservacionPrecioLocal.CLASIFICACION_REVISAR)

    def test_fila_precio_a_cargar_crea_objetivo(self):
        preview = previsualizar_importacion_local(TABLA_LOCAL, fecha_observacion=timezone.now(), zona="Salta Capital")
        lote = confirmar_importacion_local(
            {"nombre": "Tabla local", "fecha_observacion": timezone.now(), "zona": "Salta Capital", "metodo_captura": LoteCapturaLocal.METODO_TABLA_MARKDOWN, "estado": LoteCapturaLocal.ESTADO_BORRADOR, "hash_importacion": preview["hash"]},
            preview["filas"],
            TABLA_LOCAL,
        )
        self.assertEqual(lote.observaciones_precio.count(), 2)
        self.assertEqual(lote.objetivos.count(), 1)
        self.assertEqual(lote.objetivos.first().nombre_objetivo, "Arroz economico")

    def test_precio_cero_rechazado(self):
        obs = self._obs(precio=Decimal("0.00"))
        self.assertEqual(obs.clasificacion_automatica, ObservacionPrecioLocal.CLASIFICACION_DESCARTAR)

    def test_observacion_vencida(self):
        obs = self._obs(estado_vigencia=ObservacionPrecioLocal.VIGENCIA_VENCIDA)
        self.assertEqual(obs.clasificacion_automatica, ObservacionPrecioLocal.CLASIFICACION_DESCARTAR)

    def test_producto_agotado(self):
        obs = self._obs(stock_estimado=ObservacionPrecioLocal.STOCK_AGOTADO)
        self.assertEqual(obs.clasificacion_automatica, ObservacionPrecioLocal.CLASIFICACION_DESCARTAR)

    def test_evidencia_pendiente(self):
        obs = self._obs()
        obs.save()
        evidencia = EvidenciaLocal.objects.create(observacion=obs, nivel_verificacion=EvidenciaLocal.NIVEL_PENDIENTE, tipo=EvidenciaLocal.TIPO_TEXTO)
        self.assertEqual(evidencia.nivel_verificacion, EvidenciaLocal.NIVEL_PENDIENTE)

    def test_clasificacion_automatica(self):
        obs = self._obs()
        self.assertIn("umbral fuerte", obs.motivo_clasificacion)

    def test_correccion_manual_auditada(self):
        from oportunidades.models import CorreccionClasificacionLocal

        obs = self._obs()
        obs.save()
        corr = CorreccionClasificacionLocal.objects.create(
            observacion=obs,
            clasificacion_anterior=obs.clasificacion_final,
            clasificacion_nueva=ObservacionPrecioLocal.CLASIFICACION_REVISAR,
            motivo="Revisar vencimiento.",
        )
        self.assertEqual(corr.clasificacion_nueva, ObservacionPrecioLocal.CLASIFICACION_REVISAR)

    def test_importacion_markdown(self):
        preview = previsualizar_importacion_local(TABLA_LOCAL, formato="markdown")
        self.assertEqual(preview["total"], 3)
        self.assertEqual(preview["filas"][1]["normalizacion"]["precio_por_kg"], "1000.00")

    def test_importacion_csv(self):
        csv = "Ranking,Producto,Fuente,Zona,Precio encontrado,Presentacion,Unidad normalizada\n1,Aceite,Mayorista,Salta,2250,900 ml,$/litro\n"
        preview = previsualizar_importacion_local(csv, formato="csv")
        self.assertEqual(preview["filas"][0]["normalizacion"]["precio_por_litro"], "2500.00")

    def test_deteccion_de_duplicados(self):
        fecha = timezone.now()
        preview = previsualizar_importacion_local(TABLA_LOCAL, fecha_observacion=fecha)
        confirmar_importacion_local({"nombre": "Tabla local", "fecha_observacion": fecha, "zona": "Salta Capital", "metodo_captura": LoteCapturaLocal.METODO_TABLA_MARKDOWN, "estado": LoteCapturaLocal.ESTADO_BORRADOR, "hash_importacion": preview["hash"]}, preview["filas"], TABLA_LOCAL)
        preview2 = previsualizar_importacion_local(TABLA_LOCAL, fecha_observacion=fecha)
        self.assertIsNotNone(preview2["duplicado"])

    def test_pantalla_carga_desde_celular(self):
        user = get_user_model().objects.create_user("admin", password="x", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(reverse("oportunidades:local_registrar_precio"))
        self.assertContains(response, "Registrar precio local")

    def test_ranking_local_separado(self):
        response = self.client.get(reverse("oportunidades:oportunidades_locales_salta"))
        self.assertEqual(response.status_code, 200)

    def test_permisos_publicacion_importacion(self):
        response = self.client.post(reverse("oportunidades:local_importar"), {})
        self.assertEqual(response.status_code, 403)

    def test_api_publica_solo_publicados(self):
        obs_borrador = self._obs()
        obs_borrador.estado_publicacion = LoteCapturaLocal.ESTADO_BORRADOR
        obs_borrador.save()
        obs_publica = self._obs(nombre="Fideos publicado")
        obs_publica.estado_publicacion = LoteCapturaLocal.ESTADO_PUBLICADO
        obs_publica.save()
        response = self.client.get(reverse("oportunidades:api_locales_oportunidades"))
        self.assertEqual(response.status_code, 200)
        nombres = [row["nombre_original"] for row in response.json()]
        self.assertEqual(nombres, ["Fideos publicado"])
