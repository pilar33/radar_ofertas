from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from oportunidades.services.clasificacion_service import clasificar_oportunidad
from oportunidades.services.margen_service import calcular_margen, calcular_porcentaje_margen


def _producto(es_chico_liviano=True, es_fragil=False, vendedor="Vendedor Demo"):
    return SimpleNamespace(
        es_chico_liviano=es_chico_liviano,
        es_fragil=es_fragil,
        vendedor=vendedor,
        fuente=SimpleNamespace(activa=True),
        categoria=SimpleNamespace(activa=True),
    )


class ServiciosComercialesTests(SimpleTestCase):
    def test_calcular_margen(self):
        margen = calcular_margen(
            Decimal("100.00"),
            Decimal("150.00"),
            costo_envio=Decimal("10.00"),
            costo_embalaje=Decimal("5.00"),
            otros_costos=Decimal("5.00"),
        )

        self.assertEqual(margen, Decimal("30.00"))

    def test_calcular_porcentaje_margen(self):
        porcentaje = calcular_porcentaje_margen(Decimal("100.00"), Decimal("35.00"))

        self.assertEqual(porcentaje, Decimal("35.00"))

    def test_clasificar_reventa(self):
        resultado = clasificar_oportunidad(_producto(), Decimal("100.00"), Decimal("145.00"))

        self.assertEqual(resultado["tipo"], "reventa")
        self.assertIn(resultado["riesgo"], ["bajo", "medio"])
        self.assertGreaterEqual(resultado["puntaje"], 75)

    def test_clasificar_afiliado(self):
        resultado = clasificar_oportunidad(_producto(), Decimal("100.00"), Decimal("115.00"))

        self.assertEqual(resultado["tipo"], "afiliado")
        self.assertEqual(resultado["riesgo"], "medio")
        self.assertGreaterEqual(resultado["puntaje"], 50)
        self.assertLessEqual(resultado["puntaje"], 80)

    def test_clasificar_descartar(self):
        resultado = clasificar_oportunidad(_producto(), Decimal("100.00"), Decimal("80.00"))

        self.assertEqual(resultado["tipo"], "descartar")
        self.assertEqual(resultado["riesgo"], "alto")
        self.assertLess(resultado["puntaje"], 50)
