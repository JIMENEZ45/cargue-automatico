"""
============================================================
MOTOR PRIZMA - AUTOMATIZACION CON PLAYWRIGHT
============================================================

Reglas criticas que este modulo respeta siempre:

  1. Todos los archivos se cargan en el campo RECURSO.
  2. Material descargable NUNCA se toca.
  3. Si el campo Recurso no se identifica de forma unica: no se guarda.
  4. La actividad se identifica por nombre exacto + semana + unidad
     + programa + categoria. Ante duda, no se modifica.
  5. NO_DISPONIBLE se borra solo si es el unico contenido.
  6. Despues de guardar NO se reabre la actividad.
  7. Un error en una actividad no detiene el curso.
"""

import re
from pathlib import Path

import configuracion as cfg
from nucleo import errores
from nucleo.gestor_recursos import IndiceRecursos, extraer_recurso, resolver_recurso
from nucleo.gestor_trabajos import construir_fila_reporte, generar_reporte_csv
from nucleo.lector_excel import normalizar_texto
from nucleo.registro import obtener_registro

log = obtener_registro("motor_prizma")


# ============================================================
# DISPONIBILIDAD DE PLAYWRIGHT
# ============================================================

def playwright_disponible() -> bool:
    """Indica si Playwright esta instalado en este entorno."""
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


# ============================================================
# SESION DEL NAVEGADOR
# ============================================================

class SesionPrizma:
    """Envuelve el navegador y la pagina de PRIZMA."""

    def __init__(self, sin_ventana: bool = None):
        self.sin_ventana = cfg.NAVEGADOR_SIN_VENTANA if sin_ventana is None else sin_ventana
        self._playwright = None
        self.navegador = None
        self.contexto = None
        self.pagina = None

    # --------------------------------------------------------
    def abrir(self):
        """Arranca Chromium y prepara una pagina."""
        if not playwright_disponible():
            raise errores.ErrorCargue(
                errores.ERROR_NAVEGADOR_NO_DISPONIBLE,
                "Playwright no esta instalado en este entorno.",
            )

        from playwright.sync_api import sync_playwright

        log.info("Abriendo Chromium (sin ventana=%s)", self.sin_ventana)

        self._playwright = sync_playwright().start()
        self.navegador = self._playwright.chromium.launch(
            headless=self.sin_ventana,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self.contexto = self.navegador.new_context(
            viewport={"width": 1600, "height": 950},
            accept_downloads=False,
        )
        self.contexto.set_default_timeout(cfg.ESPERA_ELEMENTO_MS)
        self.pagina = self.contexto.new_page()
        return self.pagina

    # --------------------------------------------------------
    def cerrar(self):
        """Cierra todo sin lanzar excepciones."""
        for cerrar, nombre in (
            (getattr(self.contexto, "close", None), "contexto"),
            (getattr(self.navegador, "close", None), "navegador"),
            (getattr(self._playwright, "stop", None), "playwright"),
        ):
            try:
                if cerrar:
                    cerrar()
            except Exception as fallo:
                log.warning("Fallo al cerrar %s: %s", nombre, fallo)
        log.info("Navegador cerrado")

    # --------------------------------------------------------
    def iniciar_sesion(self, usuario: str, contrasena: str) -> bool:
        """
        Inicia sesion en PRIZMA con las credenciales de esta ejecucion.
        Las credenciales nunca se registran en los logs.
        """
        pagina = self.pagina
        log.info("Abriendo pantalla de inicio de sesion")

        pagina.goto(cfg.URL_PRIZMA_LOGIN, wait_until="domcontentloaded",
                    timeout=cfg.ESPERA_NAVEGACION_MS)
        pagina.wait_for_timeout(1500)

        campo_usuario = self._detectar_campo_usuario(pagina)
        campo_contrasena = pagina.locator('input[type="password"]').first

        if not campo_usuario or campo_contrasena.count() == 0:
            raise errores.ErrorCargue(
                errores.ERROR_LOGIN_FALLIDO,
                "No se localizaron los campos del formulario de inicio de sesion.",
            )

        campo_usuario.fill(usuario)
        campo_contrasena.fill(contrasena)

        boton = self._detectar_boton_ingresar(pagina)
        if boton is None:
            campo_contrasena.press("Enter")
        else:
            boton.click()

        # Se considera exitoso cuando aparece la navegacion interna
        try:
            pagina.wait_for_selector(
                'text=/Actividades/i',
                timeout=cfg.ESPERA_NAVEGACION_MS,
            )
        except Exception:
            if pagina.locator('input[type="password"]').count() > 0:
                raise errores.ErrorCargue(
                    errores.ERROR_LOGIN_FALLIDO,
                    "PRIZMA rechazo las credenciales o requiere verificacion adicional.",
                )
            raise errores.ErrorCargue(
                errores.ERROR_LOGIN_FALLIDO,
                "No aparecio la navegacion interna despues de enviar el formulario.",
            )

        log.info("Sesion iniciada correctamente")
        return True

    # --------------------------------------------------------
    @staticmethod
    def _detectar_campo_usuario(pagina):
        """Busca el campo de usuario probando varios selectores razonables."""
        candidatos = [
            'input[type="email"]',
            'input[name="email"]',
            'input[name="username"]',
            'input[name="usuario"]',
            'input[autocomplete="username"]',
        ]
        for selector in candidatos:
            elemento = pagina.locator(selector).first
            if elemento.count() > 0:
                return elemento

        # Ultimo recurso: el primer input de texto que no sea password
        textos = pagina.locator('input[type="text"]')
        if textos.count() > 0:
            return textos.first
        return None

    # --------------------------------------------------------
    @staticmethod
    def _detectar_boton_ingresar(pagina):
        candidatos = [
            'button[type="submit"]',
            'button:has-text("Iniciar")',
            'button:has-text("Ingresar")',
            'button:has-text("Entrar")',
        ]
        for selector in candidatos:
            elemento = pagina.locator(selector).first
            if elemento.count() > 0:
                return elemento
        return None

    # --------------------------------------------------------
    def esperar_login_manual(self):
        """Modo local: el usuario inicia sesion a mano en la ventana visible."""
        log.info("Esperando inicio de sesion manual en la ventana de Chromium")
        self.pagina.goto(cfg.URL_PRIZMA_LOGIN, wait_until="domcontentloaded")
        self.pagina.wait_for_selector(
            'text=/Actividades/i', timeout=cfg.ESPERA_LOGIN_MANUAL_MS
        )
        log.info("Inicio de sesion manual detectado")


# ============================================================
# NAVEGACION AL LISTADO DE ACTIVIDADES
# ============================================================

def ir_a_actividades(pagina):
    """Entra a la seccion de actividades y espera el buscador."""
    enlace = pagina.locator('text=/^\\s*Actividades\\s*$/i').first
    if enlace.count() > 0:
        try:
            enlace.click()
        except Exception as fallo:
            log.warning("No se pudo pulsar el enlace Actividades: %s", fallo)

    pagina.wait_for_selector(cfg.SELECTOR_BUSCADOR, timeout=cfg.ESPERA_ELEMENTO_MS)
    log.info("Listado de actividades disponible")


# ============================================================
# BUSQUEDA DE LA ACTIVIDAD
# ============================================================

def _texto_fila(fila) -> str:
    try:
        return normalizar_texto(fila.inner_text())
    except Exception:
        return ""


def _coincide_actividad(texto_fila: str, actividad) -> bool:
    """
    Verifica que la fila corresponde a la actividad buscada.

    Nombre: coincidencia exacta normalizada.
    Programa: coincidencia parcial, porque PRIZMA puede mostrar
              "INGENIERIA INDUSTRIAL VIRTUAL" frente a "Ingenieria Industrial".
    """
    nombre = actividad.nombre_normalizado
    if nombre not in texto_fila:
        return False

    # El nombre debe aparecer como unidad completa, no como fragmento
    patron = r"(?<![A-Z0-9])" + re.escape(nombre) + r"(?![A-Z0-9])"
    if not re.search(patron, texto_fila):
        return False

    categoria = normalizar_texto(actividad.categoria)
    if categoria and categoria not in texto_fila:
        return False

    return True


def _fila_de_la_actividad(pagina, actividad):
    """
    Recorre las filas visibles y devuelve las que coinciden.
    Una fila valida es un contenedor con exactamente 3 botones.
    """
    coincidencias = []
    filas = pagina.locator("tbody tr")
    total_filas = filas.count()

    if total_filas == 0:
        filas = pagina.locator('[role="row"]')
        total_filas = filas.count()

    for indice in range(total_filas):
        fila = filas.nth(indice)
        texto = _texto_fila(fila)
        if not texto:
            continue
        if not _coincide_actividad(texto, actividad):
            continue
        if fila.locator("button").count() != 3:
            continue
        coincidencias.append(fila)

    return coincidencias


def _ir_a_pagina_siguiente(pagina) -> bool:
    """Avanza a la siguiente pagina de resultados. Devuelve False si no hay mas."""
    candidatos = [
        'button[aria-label="Go to next page"]',
        'button[aria-label*="siguiente" i]',
        'button[title*="siguiente" i]',
        '[aria-label="Next page"]',
    ]
    for selector in candidatos:
        boton = pagina.locator(selector).first
        if boton.count() == 0:
            continue
        if boton.is_disabled():
            return False
        try:
            boton.click()
            pagina.wait_for_timeout(1200)
            return True
        except Exception:
            return False
    return False


def buscar_actividad_correcta(pagina, actividad):
    """
    Busca la actividad recorriendo TODAS las paginas de resultados.

      0 coincidencias  -> ERROR_ACTIVIDAD_NO_ENCONTRADA
    > 1 coincidencia   -> ERROR_ACTIVIDAD_DUPLICADA
      1 coincidencia   -> se devuelve la fila
    """
    buscador = pagina.locator(cfg.SELECTOR_BUSCADOR).first
    if buscador.count() == 0:
        raise errores.ErrorCargue(
            errores.ERROR_RECUPERANDO_PAGINA, "No se encontro el buscador."
        )

    buscador.fill("")
    buscador.fill(actividad.nombre)
    pagina.wait_for_timeout(1800)

    encontradas = []
    numero_pagina = 1
    limite_paginas = 60

    while numero_pagina <= limite_paginas:
        try:
            encontradas.extend(_fila_de_la_actividad(pagina, actividad))
        except Exception as fallo:
            raise errores.ErrorCargue(
                errores.ERROR_RECUPERANDO_PAGINA,
                f"Pagina {numero_pagina}: {fallo}",
            )

        if len(encontradas) > 1:
            break
        if not _ir_a_pagina_siguiente(pagina):
            break
        numero_pagina += 1

    if len(encontradas) == 0:
        raise errores.ErrorCargue(
            errores.ERROR_ACTIVIDAD_NO_ENCONTRADA,
            f'No aparece "{actividad.nombre}" en PRIZMA.',
        )

    if len(encontradas) > 1:
        raise errores.ErrorCargue(
            errores.ERROR_ACTIVIDAD_DUPLICADA,
            f"{len(encontradas)} coincidencias exactas.",
        )

    return encontradas[0]


def abrir_edicion(pagina, fila):
    """Pulsa el segundo boton de la fila, que abre la edicion."""
    try:
        botones = fila.locator("button")
        if botones.count() != 3:
            raise errores.ErrorCargue(
                errores.ERROR_RECUPERANDO_FILA,
                f"La fila tiene {botones.count()} botones en lugar de 3.",
            )
        botones.nth(1).click()
    except errores.ErrorCargue:
        raise
    except Exception as fallo:
        raise errores.ErrorCargue(errores.ERROR_ABRIENDO_EDICION, str(fallo))

    # La URL puede no cambiar: se espera a que aparezca un input de archivo
    try:
        pagina.wait_for_selector('input[type="file"]', timeout=cfg.ESPERA_ELEMENTO_MS)
    except Exception:
        raise errores.ErrorCargue(
            errores.ERROR_ABRIENDO_EDICION,
            "No aparecio ningun campo de archivo tras abrir la edicion.",
        )

    log.info("Pantalla de edicion abierta")


# ============================================================
# DETECCION DEL CAMPO RECURSO
# ============================================================

def detectar_campo_recurso(pagina):
    """
    Devuelve el input del campo RECURSO.

    Regla: el campo Recurso acepta .h5p. El campo Material descargable
    acepta unicamente .pdf y debe ignorarse SIEMPRE.

    Si no se identifica de forma unica: ERROR_CAMPO_RECURSO_NO_ENCONTRADO.
    """
    entradas = pagina.locator('input[type="file"]')
    total = entradas.count()

    if total == 0:
        raise errores.ErrorCargue(
            errores.ERROR_CAMPO_RECURSO_NO_ENCONTRADO,
            "No hay campos de archivo en la pantalla.",
        )

    candidatos = []

    for indice in range(total):
        entrada = entradas.nth(indice)
        try:
            acepta = (entrada.get_attribute("accept") or "").lower()
        except Exception:
            continue

        # Material descargable: acepta unicamente PDF. Se descarta.
        extensiones = {e.strip() for e in acepta.split(",") if e.strip()}
        if extensiones and extensiones <= {".pdf", "application/pdf"}:
            continue

        # Campo Recurso: acepta .h5p
        if ".h5p" in acepta:
            candidatos.append((indice, entrada))

    if len(candidatos) == 0:
        raise errores.ErrorCargue(
            errores.ERROR_CAMPO_RECURSO_NO_ENCONTRADO,
            f"Ninguno de los {total} campos de archivo acepta .h5p.",
        )

    if len(candidatos) > 1:
        raise errores.ErrorCargue(
            errores.ERROR_CAMPO_RECURSO_NO_ENCONTRADO,
            f"{len(candidatos)} campos aceptan .h5p. No se puede elegir con seguridad.",
        )

    indice, entrada = candidatos[0]
    log.info("Campo Recurso identificado (input %s de %s)", indice + 1, total)
    return entrada


# ============================================================
# DESCRIPCION
# ============================================================

def limpiar_descripcion(pagina):
    """
    Borra el placeholder NO_DISPONIBLE / NO_DISPOINBLE solo si es
    el unico contenido visible del editor.

    Si hay texto legitimo junto al placeholder:
    ERROR_DESCRIPCION_CONTENIDO_ADICIONAL
    """
    editor = None
    for selector in ('div[contenteditable="true"]', ".ql-editor", "textarea"):
        posible = pagina.locator(selector).first
        if posible.count() > 0:
            editor = posible
            break

    if editor is None:
        return False

    try:
        contenido = editor.inner_text()
    except Exception:
        try:
            contenido = editor.input_value()
        except Exception:
            return False

    normalizado = normalizar_texto(contenido)
    if not normalizado:
        return False

    placeholders = {normalizar_texto(p) for p in cfg.PLACEHOLDERS_DESCRIPCION}

    if normalizado in placeholders:
        try:
            editor.click()
            pagina.keyboard.press("Control+A")
            pagina.keyboard.press("Delete")
            log.info("Placeholder de descripcion eliminado")
            return True
        except Exception as fallo:
            log.warning("No se pudo limpiar la descripcion: %s", fallo)
            return False

    # Contiene el placeholder pero tambien otro texto: no se toca
    for placeholder in placeholders:
        if placeholder in normalizado:
            raise errores.ErrorCargue(
                errores.ERROR_DESCRIPCION_CONTENIDO_ADICIONAL,
                "La descripcion contiene el placeholder junto a texto real.",
            )

    return False


# ============================================================
# CARGA DEL ARCHIVO
# ============================================================

def cargar_archivo_en_recurso(pagina, campo_recurso, ruta_archivo: Path):
    """Asigna el archivo y verifica que su nombre quede visible."""
    ruta_archivo = Path(ruta_archivo)

    try:
        campo_recurso.set_input_files(str(ruta_archivo))
    except Exception as fallo:
        raise errores.ErrorCargue(errores.ERROR_SET_INPUT_FILES, str(fallo))

    pagina.wait_for_timeout(1200)

    nombre = ruta_archivo.name
    visible = False

    try:
        if pagina.locator(f'text="{nombre}"').count() > 0:
            visible = True
    except Exception:
        pass

    if not visible:
        try:
            valor = campo_recurso.input_value()
            if valor and nombre in valor:
                visible = True
        except Exception:
            pass

    if not visible:
        try:
            cantidad = campo_recurso.evaluate("elemento => elemento.files.length")
            if cantidad and cantidad > 0:
                visible = True
        except Exception:
            pass

    if not visible:
        raise errores.ErrorCargue(
            errores.ERROR_RECURSO_NO_VISIBLE,
            f"El archivo {nombre} no quedo visible tras asignarlo.",
        )

    log.info("Archivo asignado al campo Recurso: %s", nombre)


# ============================================================
# GUARDADO Y CONFIRMACION
# ============================================================

def encontrar_boton_guardar(pagina):
    """Busca el boton Editar de tipo submit."""
    candidatos = [
        'button[type="submit"]:has-text("Editar")',
        'button[type="submit"]',
    ]
    for selector in candidatos:
        boton = pagina.locator(selector).last
        if boton.count() > 0:
            return boton

    raise errores.ErrorCargue(
        errores.ERROR_BOTON_GUARDAR,
        "No se encontro un boton Editar de tipo submit.",
    )


def guardar_y_esperar_patch(pagina, boton_guardar):
    """
    Pulsa guardar y espera la peticion PATCH de PRIZMA.

    2xx        -> exito
    otro codigo-> ERROR_PATCH_HTTP_XXX
    sin PATCH  -> ERROR_PATCH_NO_CONFIRMADO
    """
    def es_patch_actividad(respuesta):
        return (
            respuesta.request.method == "PATCH"
            and cfg.PATRON_PATCH_ACTIVIDAD in respuesta.url
        )

    try:
        with pagina.expect_response(es_patch_actividad, timeout=cfg.ESPERA_PATCH_MS) as espera:
            try:
                boton_guardar.click()
            except Exception as fallo:
                raise errores.ErrorCargue(errores.ERROR_CLIC_GUARDAR, str(fallo))
        respuesta = espera.value
    except errores.ErrorCargue:
        raise
    except Exception:
        raise errores.ErrorCargue(
            errores.ERROR_PATCH_NO_CONFIRMADO,
            f"PRIZMA no envio PATCH en {cfg.ESPERA_PATCH_MS // 1000} segundos.",
        )

    codigo = respuesta.status
    if not (200 <= codigo < 300):
        raise errores.ErrorCargue(
            errores.error_patch_http(codigo),
            f"PRIZMA respondio {codigo}.",
        )

    log.info("PATCH confirmado con codigo %s", codigo)
    return codigo


# ============================================================
# OVERLAY POSTERIOR AL GUARDADO
# ============================================================

def cerrar_overlay_y_volver(pagina):
    """
    Cierra el mensaje flotante de exito y confirma que el listado
    vuelve a estar disponible. NO se reabre la actividad.
    """
    pagina.wait_for_timeout(800)

    overlay = pagina.locator(cfg.SELECTOR_OVERLAY_EXITO).first
    if overlay.count() > 0:
        for accion in ("boton_cerrar", "escape", "clic_fuera"):
            try:
                if accion == "boton_cerrar":
                    cerrar = overlay.locator("button").first
                    if cerrar.count() > 0:
                        cerrar.click()
                elif accion == "escape":
                    pagina.keyboard.press("Escape")
                else:
                    pagina.mouse.click(12, 12)
                pagina.wait_for_timeout(600)
                if overlay.count() == 0 or not overlay.is_visible():
                    break
            except Exception:
                continue
    else:
        try:
            pagina.keyboard.press("Escape")
        except Exception:
            pass

    try:
        pagina.wait_for_selector(cfg.SELECTOR_BUSCADOR, timeout=cfg.ESPERA_ELEMENTO_MS)
    except Exception:
        raise errores.ErrorCargue(
            errores.ERROR_POST_GUARDADO_LISTADO,
            "El buscador no volvio a estar disponible tras guardar.",
        )

    log.info("Listado disponible de nuevo")


# ============================================================
# PROCESAMIENTO DE UNA ACTIVIDAD
# ============================================================

def procesar_actividad(pagina, actividad, ruta_archivo: Path):
    """
    Flujo completo de una actividad:
      buscar -> abrir -> detectar Recurso -> limpiar descripcion
      -> cargar -> guardar -> PATCH 2xx -> cerrar overlay
    NO se reabre la actividad despues de guardar.
    """
    fila = buscar_actividad_correcta(pagina, actividad)
    abrir_edicion(pagina, fila)

    campo_recurso = detectar_campo_recurso(pagina)
    limpiar_descripcion(pagina)
    cargar_archivo_en_recurso(pagina, campo_recurso, ruta_archivo)

    boton = encontrar_boton_guardar(pagina)
    guardar_y_esperar_patch(pagina, boton)
    cerrar_overlay_y_volver(pagina)


# ============================================================
# EJECUCION COMPLETA DEL CARGUE
# ============================================================

def ejecutar_cargue(trabajo, usuario: str, contrasena: str, login_manual: bool = False):
    """
    Recorre todas las actividades del trabajo.
    Un error en una actividad no detiene las demas.
    """
    from nucleo.gestor_trabajos import ESTADO_EN_PROCESO, ESTADO_FALLIDO, ESTADO_TERMINADO

    trabajo.estado = ESTADO_EN_PROCESO
    trabajo.mensaje = "Preparando el navegador"
    trabajo.total = len(trabajo.actividades)

    sesion = SesionPrizma()
    indice = IndiceRecursos(trabajo.ruta_zip)

    try:
        sesion.abrir()

        trabajo.mensaje = "Iniciando sesion en PRIZMA"
        if login_manual:
            sesion.esperar_login_manual()
        else:
            sesion.iniciar_sesion(usuario, contrasena)

        trabajo.mensaje = "Abriendo el listado de actividades"
        ir_a_actividades(sesion.pagina)

    except errores.ErrorCargue as fallo:
        trabajo.estado = ESTADO_FALLIDO
        trabajo.mensaje = f"{fallo.codigo}: {fallo.detalle}"
        log.error("Cargue detenido antes de empezar: %s", fallo.codigo)
        sesion.cerrar()
        return
    except Exception as fallo:
        trabajo.estado = ESTADO_FALLIDO
        trabajo.mensaje = f"{errores.ERROR_NO_CONTROLADO}: {fallo}"
        log.exception("Fallo no controlado durante la preparacion")
        sesion.cerrar()
        return

    trabajo.mensaje = "Procesando actividades"

    for actividad in trabajo.actividades:
        trabajo.actualizar_progreso(actividad_actual=actividad.nombre)

        try:
            # 1. Elegir el archivo dentro del ZIP
            resolucion = resolver_recurso(
                indice, actividad.nombre, actividad.referencia, actividad.extension_esperada
            )
            if not resolucion.encontrado:
                raise errores.ErrorCargue(resolucion.codigo_error, resolucion.detalle)

            actividad.archivo_asignado = resolucion.recurso.nombre_archivo

            # 2. Extraer solo ese archivo
            ruta_archivo = extraer_recurso(
                trabajo.ruta_zip,
                resolucion.recurso,
                trabajo.carpeta_fila(actividad.fila_excel),
            )

            # 3. Cargar en PRIZMA
            procesar_actividad(sesion.pagina, actividad, ruta_archivo)

            actividad.resultado = "OK"
            actividad.observacion = cfg.MENSAJE_EXITO
            trabajo.actualizar_progreso(exito=True)
            log.info("[OK] %s", actividad.nombre)

        except errores.ErrorCargue as fallo:
            actividad.resultado = "ERROR"
            actividad.observacion = f"{fallo.codigo} - {fallo.detalle or errores.explicar(fallo.codigo)}"
            trabajo.actualizar_progreso(exito=False)
            log.warning("[ERROR] %s -> %s", actividad.nombre, fallo.codigo)
            _intentar_recuperar_listado(sesion.pagina)

        except Exception as fallo:
            actividad.resultado = "ERROR"
            actividad.observacion = f"{errores.ERROR_NO_CONTROLADO} - {fallo}"
            trabajo.actualizar_progreso(exito=False)
            log.exception("[ERROR] %s -> fallo no controlado", actividad.nombre)
            _intentar_recuperar_listado(sesion.pagina)

        trabajo.registrar_fila_reporte(
            construir_fila_reporte(actividad, actividad.resultado, actividad.observacion)
        )

    sesion.cerrar()

    generar_reporte_csv(trabajo)
    trabajo.estado = ESTADO_TERMINADO
    trabajo.actividad_actual = ""
    trabajo.mensaje = (
        f"Proceso terminado. {trabajo.exitosas} exitosas, {trabajo.con_error} con error."
    )
    log.info(trabajo.mensaje)


def _intentar_recuperar_listado(pagina):
    """Tras un error, intenta dejar la pagina lista para la siguiente actividad."""
    try:
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(500)
        if pagina.locator(cfg.SELECTOR_BUSCADOR).count() == 0:
            pagina.goto(cfg.URL_PRIZMA_BASE, wait_until="domcontentloaded")
            ir_a_actividades(pagina)
    except Exception as fallo:
        log.warning("No se pudo recuperar el listado: %s", fallo)
