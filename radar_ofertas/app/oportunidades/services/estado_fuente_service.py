from oportunidades.models import ConectorFuente, ConfiguracionExtractorWeb, PoliticaExtraccionFuente


def evaluar_estado_operativo_fuente(fuente):
    faltantes = []
    politica = getattr(fuente, "politica_extraccion", None)
    conector = fuente.conectores.filter(tipo_conector=ConectorFuente.TIPO_SCRAPING_PERMITIDO).first()
    extractor = ConfiguracionExtractorWeb.objects.filter(conector=conector).first() if conector else None

    estado = "listo para preview"
    puede_preview = True
    puede_procesar = True
    requiere_js = bool(extractor and extractor.requiere_js_detectado)

    if not politica:
        faltantes.append("falta politica")
    else:
        if politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_ROJO:
            estado = "fuente restringida"
            faltantes.append("semaforo rojo")
        elif politica.semaforo == PoliticaExtraccionFuente.SEMAFORO_DESCONOCIDO:
            estado = "falta auditoria"
            faltantes.append("semaforo desconocido")
        if not politica.robots_txt_revisado:
            faltantes.append("falta robots")
        if not politica.terminos_revisados:
            faltantes.append("falta terminos")
        if not politica.permite_scraping:
            faltantes.append("no habilitada para scraping")
        if politica.requiere_login:
            faltantes.append("requiere login")
        if politica.tiene_captcha:
            faltantes.append("tiene captcha")
    if not conector:
        faltantes.append("falta conector")
    elif conector.estado != ConectorFuente.ESTADO_ACTIVO:
        faltantes.append("conector no activo")
    if not extractor:
        faltantes.append("falta extractor")
    else:
        if not extractor.habilitado:
            faltantes.append("extractor no habilitado")
        if not extractor.product_card_selector and extractor.modo_extraccion not in {
            ConfiguracionExtractorWeb.MODO_JSON_LD,
            ConfiguracionExtractorWeb.MODO_MIXTO,
        }:
            faltantes.append("falta configuracion")
        if extractor.requiere_js_detectado:
            estado = "requiere JS"
            faltantes.append("requiere JS")

    if faltantes and estado == "listo para preview":
        estado = "bloqueado por politica" if politica else "falta auditoria"
    if politica and politica.metodo_preferido == PoliticaExtraccionFuente.METODO_CSV_EXCEL:
        estado = "listo para CSV/Excel"
    puede_preview = not faltantes
    puede_procesar = puede_preview
    recomendacion = "Listo para preview controlado." if puede_preview else "Resolver: " + ", ".join(faltantes)
    return {
        "estado": estado,
        "puede_preview": puede_preview,
        "puede_procesar": puede_procesar,
        "requiere_js": requiere_js,
        "faltantes": faltantes,
        "recomendacion": recomendacion,
        "conector": conector,
        "extractor": extractor,
        "politica": politica,
    }
