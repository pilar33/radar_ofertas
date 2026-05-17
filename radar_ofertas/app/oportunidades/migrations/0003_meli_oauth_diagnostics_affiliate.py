# Generated for radar_ofertas Etapa 3.1.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("oportunidades", "0002_producto_meli_fields_consultamercadolibre"),
    ]

    operations = [
        migrations.AddField(
            model_name="consultamercadolibre",
            name="forbidden",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="consultamercadolibre",
            name="requiere_token",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="consultamercadolibre",
            name="status_code",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultamercadolibre",
            name="uso_token",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="producto",
            name="afiliado_activo",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="producto",
            name="nota_afiliado",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="producto",
            name="url_afiliado",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="MercadoLibreToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id_meli", models.CharField(blank=True, max_length=100, null=True)),
                ("nickname", models.CharField(blank=True, max_length=150, null=True)),
                ("access_token", models.TextField()),
                ("refresh_token", models.TextField(blank=True, null=True)),
                ("token_type", models.CharField(blank=True, max_length=50, null=True)),
                ("scope", models.TextField(blank=True, null=True)),
                ("expires_in", models.PositiveIntegerField(default=0)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("activo", models.BooleanField(default=True)),
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("fecha_actualizacion", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "token de Mercado Libre",
                "verbose_name_plural": "tokens de Mercado Libre",
                "ordering": ["-fecha_actualizacion"],
            },
        ),
    ]
