from django import forms

from .models import CategoriaInteres, Oportunidad


class OportunidadFiltroForm(forms.Form):
    tipo = forms.ChoiceField(required=False, choices=[("", "Todos los tipos")] + Oportunidad.TIPO_CHOICES)
    estado = forms.ChoiceField(required=False, choices=[("", "Todos los estados")] + Oportunidad.ESTADO_CHOICES)
    categoria = forms.ModelChoiceField(
        required=False,
        queryset=CategoriaInteres.objects.filter(activa=True),
        empty_label="Todas las categorias",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-select"})
