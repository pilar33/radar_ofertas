from urllib.parse import urlparse


def normalizar_dominio(dominio_o_url):
    valor = (dominio_o_url or "").strip().lower()
    if not valor:
        return ""
    if "://" not in valor:
        valor_parseable = f"//{valor}"
    else:
        valor_parseable = valor
    parsed = urlparse(valor_parseable)
    dominio = parsed.netloc or parsed.path.split("/")[0]
    dominio = dominio.strip().rstrip("/")
    if "@" in dominio:
        dominio = dominio.rsplit("@", 1)[-1]
    if ":" in dominio:
        dominio = dominio.split(":", 1)[0]
    if dominio.startswith("www."):
        dominio = dominio[4:]
    return dominio


def url_pertenece_a_dominio(url, dominio_permitido):
    dominio_url = normalizar_dominio(url)
    dominio_base = normalizar_dominio(dominio_permitido)
    return bool(dominio_url and dominio_base and dominio_url == dominio_base)
