from django import forms

from .models import CategoriaInteres, Oportunidad


class OportunidadFiltroForm(forms.Form):
    tipo = forms.ChoiceField(required=False, choices=[("", "Todos los tipos")] + Oportunidad.TIPO_CHOICES)
    estado = forms.ChoiceField(required=False, choices=[("", "Todos los estados")] + Oportunidad.ESTADO_CHOICES)
    fuente = forms.ChoiceField(required=False, choices=[("", "Todas las fuentes")])
    categoria = forms.ModelChoiceField(
        required=False,
        queryset=CategoriaInteres.objects.filter(activa=True),
        empty_label="Todas las categorias",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import FuenteProducto

        self.fields["fuente"].choices = [("", "Todas las fuentes")] + [
            (fuente.id, fuente.nombre) for fuente in FuenteProducto.objects.order_by("nombre")
        ]
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-select"})


class MercadoLibreBusquedaForm(forms.Form):
    query = forms.CharField(
        required=False,
        max_length=255,
        label="Busqueda libre",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "organizador cocina"}),
    )
    categoria = forms.ModelChoiceField(
        required=False,
        queryset=CategoriaInteres.objects.filter(activa=True),
        empty_label="Seleccionar categoria",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    limit = forms.IntegerField(
        min_value=1,
        max_value=50,
        initial=20,
        label="Limite",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    offset = forms.IntegerField(
        min_value=0,
        initial=0,
        label="Offset",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        query = cleaned_data.get("query")
        categoria = cleaned_data.get("categoria")

        if not query and not categoria:
            raise forms.ValidationError("Ingresá una busqueda o seleccioná una categoria.")

        if not query and categoria:
            cleaned_data["query"] = categoria.palabra_clave

        return cleaned_data
