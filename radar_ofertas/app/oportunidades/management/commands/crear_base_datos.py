import os

import pyodbc
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea la base de datos SQL Server configurada en .env si no existe."

    def handle(self, *args, **options):
        db_name = os.getenv("DB_NAME", "radar_ofertas")
        db_user = os.getenv("DB_USER", "sa")
        db_password = os.getenv("DB_PASSWORD", "")
        db_host = os.getenv("DB_HOST", "db")
        db_port = os.getenv("DB_PORT", "1433")

        connection_string = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={db_host},{db_port};"
            "DATABASE=master;"
            f"UID={db_user};"
            f"PWD={db_password};"
            "TrustServerCertificate=yes;"
        )

        with pyodbc.connect(connection_string, autocommit=True) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT DB_ID(?)", db_name)
            exists = cursor.fetchone()[0]

            if exists:
                self.stdout.write(self.style.SUCCESS(f"La base '{db_name}' ya existe."))
                return

            safe_db_name = db_name.replace("]", "]]")
            cursor.execute(f"CREATE DATABASE [{safe_db_name}]")
            self.stdout.write(self.style.SUCCESS(f"Base '{db_name}' creada correctamente."))
