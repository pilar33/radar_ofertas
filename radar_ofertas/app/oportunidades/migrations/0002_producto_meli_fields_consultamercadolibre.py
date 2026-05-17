# Generated for radar_ofertas Etapa 3.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("oportunidades", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="producto",
            name="cantidad_vendida",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="producto",
            name="disponible",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="producto",
            name="raw_data",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="producto",
            name="thumbnail_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ConsultaMercadoLibre",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query", models.CharField(max_length=255)),
                ("site_id", models.CharField(default="MLA", max_length=10)),
                ("limit", models.PositiveIntegerField(default=20)),
                ("offset", models.PositiveIntegerField(default=0)),
                ("cantidad_resultados", models.PositiveIntegerField(default=0)),
                ("exitosa", models.BooleanField(default=False)),
                ("mensaje_error", models.TextField(blank=True, null=True)),
                ("fecha_consulta", models.DateTimeField(auto_now_add=True)),
                (
                    "categoria",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="oportunidades.categoriainteres",
                    ),
                ),
            ],
            options={
                "verbose_name": "consulta de Mercado Libre",
                "verbose_name_plural": "consultas de Mercado Libre",
                "ordering": ["-fecha_consulta"],
            },
        ),
    ]
