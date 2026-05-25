from django import forms

from .models import CategoriaInteres, ConectorFuente, FuenteWeb, Oportunidad, PoliticaExtraccionFuente, PrecioFuente


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
    usar_token_si_existe = forms.BooleanField(
        required=False,
        initial=True,
        label="Usar token si esta disponible",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
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


class ImportacionProductosForm(forms.Form):
    MAX_FILE_SIZE = 10 * 1024 * 1024
    EXTENSIONES_PERMITIDAS = (".csv", ".xlsx", ".xls")

    fuente_web = forms.ModelChoiceField(
        queryset=FuenteWeb.objects.filter(activa=True),
        label="Fuente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    archivo = forms.FileField(label="Archivo CSV/Excel", widget=forms.FileInput(attrs={"class": "form-control"}))
    categoria_default = forms.ModelChoiceField(
        required=False,
        queryset=CategoriaInteres.objects.filter(activa=True),
        empty_label="Sin categoria default",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    origen_dato = forms.ChoiceField(
        choices=[
            (PrecioFuente.ORIGEN_CSV_EXCEL, "CSV/Excel"),
            (PrecioFuente.ORIGEN_MANUAL, "Manual"),
            (PrecioFuente.ORIGEN_OTRO, "Otro"),
        ],
        initial=PrecioFuente.ORIGEN_CSV_EXCEL,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    crear_producto_canonico = forms.BooleanField(
        required=False,
        initial=True,
        label="Crear o vincular producto canonico",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    actualizar_productos_existentes = forms.BooleanField(
        required=False,
        initial=True,
        label="Actualizar productos existentes",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    crear_precio_si_no_cambio = forms.BooleanField(
        required=False,
        initial=False,
        label="Crear precio aunque no haya cambio",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        nombre = archivo.name.lower()
        if not nombre.endswith(self.EXTENSIONES_PERMITIDAS):
            raise forms.ValidationError("Solo se permiten archivos .csv, .xlsx o .xls.")
        if archivo.size > self.MAX_FILE_SIZE:
            raise forms.ValidationError("El archivo no puede superar los 10 MB.")
        return archivo

    def clean_fuente_web(self):
        fuente = self.cleaned_data["fuente_web"]
        if not fuente.activa:
            raise forms.ValidationError("La fuente seleccionada no esta activa.")
        return fuente

    def get_warning(self):
        fuente = self.cleaned_data.get("fuente_web") if hasattr(self, "cleaned_data") else None
        politica = getattr(fuente, "politica_extraccion", None)
        if politica and politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_ROJO:
            return "La fuente esta marcada en rojo. La importacion solo carga un archivo provisto, no hace scraping."
        return None


class CargaProductoURLForm(forms.Form):
    fuente_web = forms.ModelChoiceField(
        queryset=FuenteWeb.objects.filter(activa=True),
        label="Fuente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    url_producto = forms.URLField(label="URL del producto", widget=forms.URLInput(attrs={"class": "form-control"}))
    titulo = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    precio = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "$ 1.200,50"}))
    categoria = forms.ModelChoiceField(
        queryset=CategoriaInteres.objects.filter(activa=True),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    marca = forms.CharField(required=False, max_length=100, widget=forms.TextInput(attrs={"class": "form-control"}))
    descripcion = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    imagen_url = forms.URLField(required=False, widget=forms.URLInput(attrs={"class": "form-control"}))
    precio_lista = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    costo_envio = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    moneda = forms.CharField(
        initial="ARS",
        max_length=10,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    es_chico_liviano = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    es_fragil = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))

    def clean_fuente_web(self):
        fuente = self.cleaned_data["fuente_web"]
        if not fuente.activa:
            raise forms.ValidationError("La fuente seleccionada no esta activa.")
        return fuente


class ConectorCatalogoForm(forms.Form):
    fuente_web = forms.ModelChoiceField(
        queryset=FuenteWeb.objects.filter(activa=True),
        label="Fuente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    nombre = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-control"}))
    tipo_conector = forms.ChoiceField(
        choices=[
            (ConectorFuente.TIPO_CSV_MANUAL, "CSV manual"),
            (ConectorFuente.TIPO_EXCEL_MANUAL, "Excel manual"),
            (ConectorFuente.TIPO_CSV_REMOTO, "CSV remoto"),
            (ConectorFuente.TIPO_EXCEL_REMOTO, "Excel remoto"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    url_recurso = forms.URLField(required=False, widget=forms.URLInput(attrs={"class": "form-control"}))
    formato_recurso = forms.ChoiceField(
        choices=ConectorFuente.FORMATO_CHOICES,
        initial=ConectorFuente.FORMATO_DESCONOCIDO,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fuente_autorizo_uso = forms.BooleanField(
        required=False,
        label="La fuente autorizo el uso del catalogo",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    frecuencia_sugerida = forms.CharField(required=False, max_length=100, widget=forms.TextInput(attrs={"class": "form-control"}))
    descripcion = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    notas_uso_datos = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))

    def clean(self):
        cleaned_data = super().clean()
        fuente = cleaned_data.get("fuente_web")
        tipo = cleaned_data.get("tipo_conector")
        url = cleaned_data.get("url_recurso")
        autorizado = cleaned_data.get("fuente_autorizo_uso")
        remoto = tipo in {ConectorFuente.TIPO_CSV_REMOTO, ConectorFuente.TIPO_EXCEL_REMOTO}

        if remoto and not url:
            raise forms.ValidationError("Los conectores remotos requieren URL directa al archivo CSV/Excel.")
        if remoto and fuente:
            politica = getattr(fuente, "politica_extraccion", None)
            if not autorizado and not (politica and politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_VERDE):
                raise forms.ValidationError("Para conectores remotos se requiere autorizacion de uso o fuente verde.")
        return cleaned_data
