import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from oportunidades.services.base_datos_service import obtener_diagnostico_base_datos


class Etapa314BaseDatosTests(TestCase):
    def test_diagnostico_no_expone_password(self):
        with override_settings(
            DATABASES={
                "default": {
                    "ENGINE": "mssql",
                    "NAME": "radar_ofertas",
                    "USER": "sa",
                    "PASSWORD": "secreto-super-privado",
                    "HOST": "db",
                    "PORT": "1433",
                }
            }
        ):
            diagnostico = obtener_diagnostico_base_datos()

        self.assertNotIn("secreto-super-privado", str(diagnostico))

    def test_diagnostico_detecta_sqlite(self):
        sqlite_settings = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": "db.sqlite3",
            }
        }
        with patch("oportunidades.services.base_datos_service.settings.DATABASES", sqlite_settings):
            with patch("oportunidades.services.base_datos_service.connection", Mock(vendor="sqlite")):
                diagnostico = obtener_diagnostico_base_datos()

        self.assertTrue(diagnostico["is_sqlite"])
        self.assertFalse(diagnostico["is_sqlserver"])

    @patch("oportunidades.services.base_datos_service.es_render", return_value=True)
    def test_diagnostico_detecta_render_sqlite_no_persistente(self, _mock_render):
        sqlite_settings = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": "db.sqlite3",
            }
        }
        with patch("oportunidades.services.base_datos_service.settings.DATABASES", sqlite_settings):
            with patch("oportunidades.services.base_datos_service.connection", Mock(vendor="sqlite")):
                diagnostico = obtener_diagnostico_base_datos()

        self.assertFalse(diagnostico["persistente"])
        self.assertIn("SQLite en Render", diagnostico["advertencia"])

    def test_diagnostico_detecta_sqlserver(self):
        sqlserver_settings = {
            "default": {
                "ENGINE": "mssql",
                "NAME": "radar_ofertas",
                "HOST": "db",
                "PORT": "1433",
            }
        }
        with patch("oportunidades.services.base_datos_service.settings.DATABASES", sqlserver_settings):
            with patch("oportunidades.services.base_datos_service.connection", Mock(vendor="microsoft")):
                diagnostico = obtener_diagnostico_base_datos()

        self.assertTrue(diagnostico["is_sqlserver"])
        self.assertTrue(diagnostico["persistente"])

    def test_vista_base_datos_carga(self):
        response = Client(HTTP_HOST="localhost").get("/sistema/base-datos/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Base de datos activa")

    def test_backup_rapido_dataset_crea_archivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("backup_rapido_dataset", "--base-dir", tmpdir)
            archivos = list(Path(tmpdir).rglob("*"))

        nombres = [archivo.name for archivo in archivos]
        self.assertTrue(any(nombre.startswith("snapshot_radar_") for nombre in nombres))
        self.assertTrue(any(nombre.startswith("productos_dataset_") for nombre in nombres))
        self.assertTrue(any(nombre.startswith("historial_precios_") for nombre in nombres))
        self.assertTrue(any(nombre.startswith("radar_dataset_") for nombre in nombres))

    def test_docs_base_datos_sqlserver_existe(self):
        doc_path = Path(__file__).resolve().parents[1] / "docs" / "base_datos_principal_sqlserver.md"

        self.assertTrue(doc_path.exists())
        self.assertIn("SQL Server", doc_path.read_text(encoding="utf-8"))
