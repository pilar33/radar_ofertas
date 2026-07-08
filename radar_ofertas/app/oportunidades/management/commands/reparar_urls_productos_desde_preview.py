from django.core.management.base import BaseCommand
from django.db.models import Q

from oportunidades.models import ProductoFuente, ResultadoExtraccionWeb, ResultadoLaboratorioMapeo
from oportunidades.services.normalizacion_service import normalizar_texto_producto


def _url_real(url):
    return bool(url and "/radar-preview/" not in url)


class Command(BaseCommand):
    help = "Repara URL tecnicas de ProductoFuente usando URLs reales ya detectadas en previews o laboratorio."

    def add_arguments(self, parser):
        parser.add_argument("--fuente-id", type=int, default=None)
        parser.add_argument("--lote-id", type=int, default=None)
        parser.add_argument("--limite", type=int, default=50)

    def handle(self, *args, **options):
        productos = ProductoFuente.objects.filter(url_tecnica_generada=True).select_related("fuente_web", "lote_origen")
        if options["fuente_id"]:
            productos = productos.filter(fuente_web_id=options["fuente_id"])
        if options["lote_id"]:
            productos = productos.filter(Q(lote_origen_id=options["lote_id"]) | Q(detallelotecaptura__lote_id=options["lote_id"])).distinct()

        revisados = 0
        corregidos = 0
        limite = max(options["limite"], 0)
        for producto in productos.order_by("-fecha_actualizacion")[:limite]:
            revisados += 1
            titulo_normalizado = normalizar_texto_producto(producto.titulo_original)
            candidatos_preview = ResultadoExtraccionWeb.objects.filter(
                ejecucion__conector__fuente_web=producto.fuente_web,
                url_producto__isnull=False,
            ).exclude(url_producto="")
            if producto.lote_origen_id:
                candidatos_preview = candidatos_preview.filter(lote_captura=producto.lote_origen)
            url = None
            for resultado in candidatos_preview.order_by("-fecha_creacion")[:200]:
                if _url_real(resultado.url_producto) and normalizar_texto_producto(resultado.titulo) == titulo_normalizado:
                    url = resultado.url_producto
                    break
            if not url:
                candidatos_laboratorio = ResultadoLaboratorioMapeo.objects.filter(
                    sesion__fuente_web=producto.fuente_web,
                    url_producto__isnull=False,
                ).exclude(url_producto="")
                if producto.lote_origen_id:
                    candidatos_laboratorio = candidatos_laboratorio.filter(lote_captura=producto.lote_origen)
                for resultado in candidatos_laboratorio.order_by("-id")[:200]:
                    if _url_real(resultado.url_producto) and normalizar_texto_producto(resultado.titulo) == titulo_normalizado:
                        url = resultado.url_producto
                        break
            if not url:
                continue
            producto.url_producto = url
            producto.url_tecnica_generada = False
            producto.save(update_fields=["url_producto", "url_tecnica_generada", "fecha_actualizacion"])
            corregidos += 1

        self.stdout.write(self.style.SUCCESS(f"Revisados={revisados}, corregidos={corregidos}."))
