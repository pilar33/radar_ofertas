from urllib.parse import urljoin, urlparse, urlunparse

import requests
from django.utils import timezone

from oportunidades.models import (
    AuditoriaFuenteWeb,
    DecisionTecnica,
    PoliticaExtraccionFuente,
    RecursoFuenteDetectado,
)
from oportunidades.services.documentacion_service import registrar_decision_tecnica


MAX_PREVIEW_BYTES = 200 * 1024
HEADERS = {
    "User-Agent": "radar_ofertas/1.0",
    "Accept-Language": "es-AR,es;q=0.9",
    "Accept": "text/plain,text/html,application/xml,text/xml,*/*;q=0.8",
}


def normalizar_url_base(url):
    parsed = urlparse((url or "").strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{url.strip()}")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path or "", "", "", ""))


def obtener_url_robots(url_base):
    return urljoin(normalizar_url_base(url_base) + "/", "robots.txt")


def obtener_url_sitemap(url_base):
    return urljoin(normalizar_url_base(url_base) + "/", "sitemap.xml")


def hacer_request_controlado(url, timeout=15):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=8192, decode_unicode=False):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_PREVIEW_BYTES:
                break
        raw = b"".join(chunks)[:MAX_PREVIEW_BYTES]
        encoding = response.encoding or "utf-8"
        text_preview = raw.decode(encoding, errors="replace")
        return {
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "content_type": (response.headers.get("Content-Type") or "").split(";")[0].strip(),
            "text_preview": text_preview[:4000],
            "error": "",
        }
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "content_type": "", "text_preview": "", "error": str(exc)}


def _detectar_senales(*textos):
    texto = " ".join(texto or "" for texto in textos).lower()
    return {
        "captcha": any(p in texto for p in ["captcha", "recaptcha", "cloudflare challenge"]),
        "login": any(p in texto for p in ["login", "iniciar sesion", "iniciar sesión", "mi cuenta"]),
        "bloqueo": any(p in texto for p in ["forbidden", "access denied", "blocked", "policy"]),
    }


def _sugerir(home, robots, sitemap, senales):
    statuses = [home.get("status_code"), robots.get("status_code"), sitemap.get("status_code")]
    bloqueo_403 = any(status == 403 for status in statuses if status is not None)
    if bloqueo_403 or senales["captcha"]:
        return (
            PoliticaExtraccionFuente.SEMAFORO_ROJO,
            AuditoriaFuenteWeb.METODO_NO_AUTOMATIZAR,
            AuditoriaFuenteWeb.PERMITE_NO,
        )
    if sitemap.get("ok"):
        return (
            PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            AuditoriaFuenteWeb.METODO_SITEMAP,
            AuditoriaFuenteWeb.PERMITE_DUDOSO,
        )
    if home.get("ok") and robots.get("ok"):
        return (
            PoliticaExtraccionFuente.SEMAFORO_AMARILLO,
            AuditoriaFuenteWeb.METODO_PENDIENTE_REVISION,
            AuditoriaFuenteWeb.PERMITE_DUDOSO,
        )
    if home.get("ok"):
        return (
            PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
            AuditoriaFuenteWeb.METODO_CARGA_URL,
            AuditoriaFuenteWeb.PERMITE_PENDIENTE,
        )
    return (
        PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO,
        AuditoriaFuenteWeb.METODO_PENDIENTE_REVISION,
        AuditoriaFuenteWeb.PERMITE_PENDIENTE,
    )


def auditar_fuente_basica(fuente_web):
    url_base = normalizar_url_base(fuente_web.url_base)
    robots_url = obtener_url_robots(url_base)
    sitemap_url = obtener_url_sitemap(url_base)

    home = hacer_request_controlado(url_base)
    robots = hacer_request_controlado(robots_url)
    sitemap = hacer_request_controlado(sitemap_url)
    senales = _detectar_senales(home["text_preview"], robots["text_preview"], sitemap["text_preview"])
    semaforo, metodo, permite = _sugerir(home, robots, sitemap, senales)
    riesgos = []
    if senales["captcha"]:
        riesgos.append("Se detectaron senales de captcha/challenge.")
    if senales["login"]:
        riesgos.append("Se detectaron referencias a login o cuenta.")
    if senales["bloqueo"]:
        riesgos.append("Se detectaron senales de bloqueo.")
    if any(status == 403 for status in [home["status_code"], robots["status_code"], sitemap["status_code"]]):
        riesgos.append("Hay respuestas 403 en recursos basicos.")

    auditoria = AuditoriaFuenteWeb.objects.create(
        fuente_web=fuente_web,
        url_robots_txt=robots_url,
        robots_txt_encontrado=bool(robots["ok"] and robots["text_preview"]),
        robots_txt_contenido_resumen=robots["text_preview"][:2000] or None,
        sitemap_detectado=bool(sitemap["ok"] and sitemap["text_preview"]),
        sitemap_url=sitemap_url if sitemap["ok"] else None,
        requiere_login_detectado=senales["login"],
        captcha_detectado=senales["captcha"],
        bloqueos_detectados=senales["bloqueo"] or any(
            status == 403 for status in [home["status_code"], robots["status_code"], sitemap["status_code"]]
        ),
        status_home=home["status_code"],
        status_robots=robots["status_code"],
        status_sitemap=sitemap["status_code"],
        permite_extraccion_segun_revision=permite,
        metodo_recomendado=metodo,
        semaforo_sugerido=semaforo,
        resumen_tecnico=(
            f"Home status={home['status_code']}; robots status={robots['status_code']}; "
            f"sitemap status={sitemap['status_code']}."
        ),
        riesgos_detectados="\n".join(riesgos) or "Sin riesgos tecnicos fuertes detectados en revision basica.",
        recomendacion=(
            "No automatizar productos todavia. Revisar terminos manualmente y priorizar CSV/Excel, API, sitemap o carga URL."
        ),
    )

    for tipo, url, resultado, permitido in [
        (RecursoFuenteDetectado.TIPO_PAGINA_INFO, url_base, home, bool(home["ok"])),
        (RecursoFuenteDetectado.TIPO_ROBOTS, robots_url, robots, bool(robots["ok"])),
        (RecursoFuenteDetectado.TIPO_SITEMAP, sitemap_url, sitemap, bool(sitemap["ok"])),
    ]:
        RecursoFuenteDetectado.objects.create(
            auditoria=auditoria,
            tipo_recurso=tipo,
            url=url,
            status_code=resultado["status_code"],
            content_type=resultado["content_type"],
            permitido=permitido,
            observaciones=resultado["error"] or resultado["text_preview"][:500],
        )

    registrar_decision_tecnica(
        titulo=f"Auditoria inicial de fuente {fuente_web.nombre}",
        categoria=DecisionTecnica.CATEGORIA_SCRAPING,
        descripcion=f"Auditoria basica de home, robots.txt y sitemap para {fuente_web.nombre}.",
        decision=f"Semaforo sugerido: {auditoria.semaforo_sugerido}. Metodo recomendado: {auditoria.metodo_recomendado}.",
        motivo=auditoria.riesgos_detectados,
        impacto="No se habilita scraping productivo en esta etapa.",
    )
    return auditoria


def interpretar_auditoria(auditoria):
    return (
        f"Se probo home, robots.txt y sitemap. Home={auditoria.status_home}, "
        f"robots={auditoria.status_robots}, sitemap={auditoria.status_sitemap}. "
        f"Semaforo sugerido: {auditoria.semaforo_sugerido}. "
        f"Metodo recomendado: {auditoria.metodo_recomendado}. "
        f"Recomendacion: {auditoria.recomendacion}"
    )


def actualizar_politica_desde_auditoria(auditoria, aplicar=False):
    politica, _ = PoliticaExtraccionFuente.objects.get_or_create(fuente=auditoria.fuente_web)
    cambios = {
        "semaforo": auditoria.semaforo_sugerido,
        "metodo_preferido": (
            PoliticaExtraccionFuente.METODO_CARGA_URL
            if auditoria.metodo_recomendado == AuditoriaFuenteWeb.METODO_CARGA_URL
            else PoliticaExtraccionFuente.METODO_PENDIENTE_REVISION
        ),
        "requiere_login": auditoria.requiere_login_detectado,
        "tiene_captcha": auditoria.captcha_detectado,
        "robots_txt_revisado": auditoria.robots_txt_encontrado,
        "fecha_revision": timezone.now(),
        "observaciones": interpretar_auditoria(auditoria),
    }
    if auditoria.metodo_recomendado == AuditoriaFuenteWeb.METODO_CSV_EXCEL:
        cambios["metodo_preferido"] = PoliticaExtraccionFuente.METODO_CSV_EXCEL
    if auditoria.metodo_recomendado == AuditoriaFuenteWeb.METODO_NO_AUTOMATIZAR:
        cambios["metodo_preferido"] = PoliticaExtraccionFuente.METODO_NO_PERMITIDO
    if aplicar:
        for campo, valor in cambios.items():
            setattr(politica, campo, valor)
        politica.save()
    return cambios
