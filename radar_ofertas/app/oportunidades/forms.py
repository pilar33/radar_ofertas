from decimal import Decimal
from urllib.parse import urlparse

from django import forms

from .models import (
    CategoriaInteres,
    ConectorFuente,
    ConfiguracionExtractorWeb,
    FuenteWeb,
    Oportunidad,
    PoliticaExtraccionFuente,
    PrecioFuente,
    ProductoFuente,
    RevisionManualFuente,
    SenalDemandaProducto,
)
from .services.dominios_service import normalizar_dominio, url_pertenece_a_dominio


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


class ProductoFuenteCuraduriaForm(forms.ModelForm):
    class Meta:
        model = ProductoFuente
        fields = [
            "titulo_original",
            "producto_canonico",
            "url_producto",
            "imagen_url",
            "marca_detectada",
            "descripcion_original",
            "vendedor",
            "condicion",
            "disponible",
            "stock_texto",
            "requiere_revision",
            "revisado",
            "motivo_revision",
            "url_tecnica_generada",
            "nota_curaduria",
            "descartado_curaduria",
        ]
        widgets = {
            "titulo_original": forms.TextInput(attrs={"class": "form-control"}),
            "producto_canonico": forms.Select(attrs={"class": "form-select"}),
            "url_producto": forms.URLInput(attrs={"class": "form-control"}),
            "imagen_url": forms.URLInput(attrs={"class": "form-control"}),
            "marca_detectada": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion_original": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "vendedor": forms.TextInput(attrs={"class": "form-control"}),
            "condicion": forms.Select(attrs={"class": "form-select"}),
            "stock_texto": forms.TextInput(attrs={"class": "form-control"}),
            "motivo_revision": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "nota_curaduria": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "disponible": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "requiere_revision": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "revisado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "url_tecnica_generada": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "descartado_curaduria": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class PrecioFuenteCuraduriaForm(forms.ModelForm):
    class Meta:
        model = PrecioFuente
        fields = [
            "precio_lista",
            "precio_transferencia",
            "precio_tarjeta",
            "cuotas_texto",
            "precio_oportunidad",
            "tipo_precio_oportunidad",
            "observaciones",
        ]
        widgets = {
            "precio_lista": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "precio_transferencia": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "precio_tarjeta": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "precio_oportunidad": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cuotas_texto": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_precio_oportunidad": forms.Select(attrs={"class": "form-select"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def save(self, commit=True):
        precio = super().save(commit=False)
        if precio.precio_oportunidad:
            precio.precio = precio.precio_oportunidad
        if commit:
            precio.save()
        return precio


class SenalDemandaManualForm(forms.ModelForm):
    class Meta:
        model = SenalDemandaProducto
        fields = [
            "cantidad_vendida_visible", "texto_vendidos", "cantidad_resenas", "cantidad_preguntas",
            "calificacion", "etiqueta_mas_vendido", "etiqueta_destacado", "etiqueta_tendencia",
            "stock_visible", "texto_stock", "observaciones",
        ]
        widgets = {
            "cantidad_vendida_visible": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "texto_vendidos": forms.TextInput(attrs={"class": "form-control"}),
            "cantidad_resenas": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "cantidad_preguntas": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "calificacion": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 5, "step": "0.01"}),
            "stock_visible": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "texto_stock": forms.TextInput(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "etiqueta_mas_vendido": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "etiqueta_destacado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "etiqueta_tendencia": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


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


class RevisionManualFuenteForm(forms.ModelForm):
    class Meta:
        model = RevisionManualFuente
        fields = [
            "fuente_web",
            "tipo_revision",
            "url_revisada",
            "resultado",
            "resumen",
            "decision",
            "aplicar_a_politica",
        ]
        widgets = {
            "fuente_web": forms.Select(attrs={"class": "form-select"}),
            "tipo_revision": forms.Select(attrs={"class": "form-select"}),
            "url_revisada": forms.URLInput(attrs={"class": "form-control"}),
            "resultado": forms.Select(attrs={"class": "form-select"}),
            "resumen": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "decision": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "aplicar_a_politica": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_resumen(self):
        resumen = self.cleaned_data.get("resumen", "").strip()
        if not resumen:
            raise forms.ValidationError("El resumen es obligatorio.")
        return resumen

    def clean(self):
        cleaned_data = super().clean()
        resultado = cleaned_data.get("resultado")
        decision = (cleaned_data.get("decision") or "").strip()
        aplicar = cleaned_data.get("aplicar_a_politica")
        if resultado == RevisionManualFuente.RESULTADO_PERMITE and aplicar and not decision:
            raise forms.ValidationError("Para aplicar un resultado permite se requiere una decision explicita.")
        return cleaned_data


class FuenteWizardForm(forms.Form):
    nombre = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": "form-control"}))
    url_base = forms.URLField(widget=forms.URLInput(attrs={"class": "form-control"}))
    rubro_principal = forms.CharField(required=False, max_length=150, widget=forms.TextInput(attrs={"class": "form-control"}))
    tipo_fuente = forms.ChoiceField(choices=FuenteWeb.TIPO_CHOICES, widget=forms.Select(attrs={"class": "form-select"}))
    pais = forms.CharField(initial="Argentina", max_length=80, widget=forms.TextInput(attrs={"class": "form-control"}))
    moneda_principal = forms.CharField(initial="ARS", max_length=10, widget=forms.TextInput(attrs={"class": "form-control"}))


class FuenteRapidaPreviewForm(forms.Form):
    PLATAFORMA_AUTO = "auto"
    PLATAFORMA_TIENDANUBE = "tiendanube"
    PLATAFORMA_SHOPIFY = "shopify"
    PLATAFORMA_WOOCOMMERCE = "woocommerce"
    PLATAFORMA_MANUAL = "manual"
    PLATAFORMA_CHOICES = [
        (PLATAFORMA_AUTO, "Detectar automaticamente"),
        (PLATAFORMA_TIENDANUBE, "Tienda Nube"),
        (PLATAFORMA_SHOPIFY, "Shopify"),
        (PLATAFORMA_WOOCOMMERCE, "WooCommerce"),
        (PLATAFORMA_MANUAL, "Manual / sin preset"),
    ]

    nombre = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ganga Home"}),
    )
    url_base = forms.URLField(
        label="URL base de la tienda",
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://www.gangahome.com.ar/"}),
    )
    url_categoria = forms.URLField(
        label="URL de categoria o prueba",
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://www.gangahome.com.ar/cocina/"}),
    )
    rubro_principal = forms.CharField(
        required=False,
        initial="hogar/deco",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    plataforma = forms.ChoiceField(choices=PLATAFORMA_CHOICES, initial=PLATAFORMA_AUTO, widget=forms.Select(attrs={"class": "form-select"}))
    revisar_como_preview = forms.BooleanField(
        required=False,
        initial=True,
        label="Habilitar solo preview controlado",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    confirmar_revision_manual = forms.BooleanField(
        required=True,
        label="Confirmo que revise robots/terminos de forma manual o acepto usar solo preview controlado",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        url_base = cleaned_data.get("url_base")
        url_categoria = cleaned_data.get("url_categoria")
        if url_base and url_categoria and urlparse(url_base).netloc != urlparse(url_categoria).netloc:
            raise forms.ValidationError("La URL de categoria debe pertenecer al mismo dominio que la URL base.")
        return cleaned_data


class ConfiguracionExtractorWebForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionExtractorWeb
        fields = [
            "pagina_prueba_url",
            "url_inicio",
            "url_categoria",
            "dominio_permitido",
            "modo_extraccion",
            "product_card_selector",
            "title_selector",
            "price_selector",
            "url_selector",
            "image_selector",
            "description_selector",
            "next_page_selector",
            "max_paginas",
            "max_productos",
            "delay_segundos",
            "timeout_segundos",
            "habilitado",
            "solo_preview",
            "observaciones",
        ]
        widgets = {
            "pagina_prueba_url": forms.URLInput(attrs={"class": "form-control"}),
            "url_inicio": forms.URLInput(attrs={"class": "form-control"}),
            "url_categoria": forms.URLInput(attrs={"class": "form-control"}),
            "dominio_permitido": forms.TextInput(attrs={"class": "form-control"}),
            "modo_extraccion": forms.Select(attrs={"class": "form-select"}),
            "product_card_selector": forms.TextInput(attrs={"class": "form-control"}),
            "title_selector": forms.TextInput(attrs={"class": "form-control"}),
            "price_selector": forms.TextInput(attrs={"class": "form-control"}),
            "url_selector": forms.TextInput(attrs={"class": "form-control"}),
            "image_selector": forms.TextInput(attrs={"class": "form-control"}),
            "description_selector": forms.TextInput(attrs={"class": "form-control"}),
            "next_page_selector": forms.TextInput(attrs={"class": "form-control"}),
            "max_paginas": forms.NumberInput(attrs={"class": "form-control"}),
            "max_productos": forms.NumberInput(attrs={"class": "form-control"}),
            "delay_segundos": forms.NumberInput(attrs={"class": "form-control", "step": "0.25"}),
            "timeout_segundos": forms.NumberInput(attrs={"class": "form-control"}),
            "habilitado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "solo_preview": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        modo = cleaned_data.get("modo_extraccion")
        dominio = cleaned_data.get("dominio_permitido")
        max_paginas = cleaned_data.get("max_paginas") or 1
        max_productos = cleaned_data.get("max_productos") or 20
        delay = cleaned_data.get("delay_segundos")
        if max_paginas > 3:
            raise forms.ValidationError("max_paginas no puede superar 3 en esta etapa.")
        if max_productos > 50:
            raise forms.ValidationError("max_productos no puede superar 50 en esta etapa.")
        if delay is not None and delay < Decimal("1.50"):
            raise forms.ValidationError("delay_segundos debe ser al menos 1.5.")
        for field in ["pagina_prueba_url", "url_inicio", "url_categoria"]:
            url = cleaned_data.get(field)
            if not url:
                continue
            if url.strip().lower().startswith(("javascript:", "data:", "mailto:")):
                raise forms.ValidationError("No se aceptan URLs javascript:, data: ni mailto:.")
            if dominio and not url_pertenece_a_dominio(url, dominio):
                raise forms.ValidationError("Las URLs del extractor deben pertenecer al dominio permitido.")
        if dominio:
            cleaned_data["dominio_permitido"] = normalizar_dominio(dominio)
        if modo == ConfiguracionExtractorWeb.MODO_CSS_SELECTORS:
            for field in ["product_card_selector", "title_selector", "price_selector"]:
                if not cleaned_data.get(field):
                    raise forms.ValidationError("CSS selectors requiere tarjeta, titulo y precio.")
        return cleaned_data


class LaboratorioMapeoForm(forms.Form):
    MODO_AUTO = "auto"
    MODO_JSON_LD = "json_ld"
    MODO_CSS_SELECTORS = "css_selectors"
    MODO_CHOICES = [
        (MODO_AUTO, "Detectar automaticamente"),
        (MODO_JSON_LD, "Usar JSON-LD"),
        (MODO_CSS_SELECTORS, "Usar selectores CSS manuales"),
    ]

    url = forms.URLField(label="URL de prueba", widget=forms.URLInput(attrs={"class": "form-control"}))
    nombre_fuente = forms.CharField(required=False, max_length=150, widget=forms.TextInput(attrs={"class": "form-control"}))
    fuente_web = forms.ModelChoiceField(
        required=False,
        queryset=FuenteWeb.objects.filter(activa=True),
        empty_label="Crear o no asociar fuente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    rubro = forms.CharField(required=False, max_length=150, widget=forms.TextInput(attrs={"class": "form-control"}))
    modo = forms.ChoiceField(choices=MODO_CHOICES, initial=MODO_AUTO, widget=forms.Select(attrs={"class": "form-select"}))
    limite = forms.IntegerField(initial=10, min_value=1, max_value=30, widget=forms.NumberInput(attrs={"class": "form-control"}))
    solo_preview = forms.BooleanField(
        required=False,
        initial=True,
        label="Solo preview, no guardar productos",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class LaboratorioSelectoresForm(forms.Form):
    url = forms.URLField(widget=forms.HiddenInput())
    sesion_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    product_card_selector = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    title_selector = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    price_selector = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    url_selector = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    image_selector = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    description_selector = forms.CharField(required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("product_card_selector"):
            raise forms.ValidationError("Indicar al menos product_card_selector.")
        return cleaned_data
