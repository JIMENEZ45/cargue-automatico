"""
============================================================
CODIGOS DE ERROR
============================================================

Todos los codigos viven aqui para evitar erratas al
escribirlos en el reporte CSV.
"""


class ErrorCargue(Exception):
    """Error controlado durante el procesamiento de una actividad."""

    def __init__(self, codigo: str, detalle: str = ""):
        self.codigo = codigo
        self.detalle = detalle
        super().__init__(f"{codigo}: {detalle}" if detalle else codigo)


# ============================================================
# RECURSOS
# ============================================================

ERROR_RECURSO_NO_ENCONTRADO = "ERROR_RECURSO_NO_ENCONTRADO"
ERROR_RECURSO_DUPLICADO = "ERROR_RECURSO_DUPLICADO"

# ============================================================
# BUSQUEDA DE ACTIVIDAD
# ============================================================

ERROR_ACTIVIDAD_NO_ENCONTRADA = "ERROR_ACTIVIDAD_NO_ENCONTRADA"
ERROR_ACTIVIDAD_DUPLICADA = "ERROR_ACTIVIDAD_DUPLICADA"
ERROR_RECUPERANDO_PAGINA = "ERROR_RECUPERANDO_PAGINA"
ERROR_RECUPERANDO_FILA = "ERROR_RECUPERANDO_FILA"
ERROR_ABRIENDO_EDICION = "ERROR_ABRIENDO_EDICION"

# ============================================================
# EDICION
# ============================================================

ERROR_CAMPO_RECURSO_NO_ENCONTRADO = "ERROR_CAMPO_RECURSO_NO_ENCONTRADO"
ERROR_DESCRIPCION_CONTENIDO_ADICIONAL = "ERROR_DESCRIPCION_CONTENIDO_ADICIONAL"
ERROR_SET_INPUT_FILES = "ERROR_SET_INPUT_FILES"
ERROR_RECURSO_NO_VISIBLE = "ERROR_RECURSO_NO_VISIBLE"

# ============================================================
# GUARDADO
# ============================================================

ERROR_BOTON_GUARDAR = "ERROR_BOTON_GUARDAR"
ERROR_CLIC_GUARDAR = "ERROR_CLIC_GUARDAR"
ERROR_PATCH_NO_CONFIRMADO = "ERROR_PATCH_NO_CONFIRMADO"
ERROR_POST_GUARDADO_LISTADO = "ERROR_POST_GUARDADO_LISTADO"

# ============================================================
# SESION
# ============================================================

ERROR_LOGIN_FALLIDO = "ERROR_LOGIN_FALLIDO"
ERROR_NAVEGADOR_NO_DISPONIBLE = "ERROR_NAVEGADOR_NO_DISPONIBLE"

# ============================================================
# GENERICO
# ============================================================

ERROR_NO_CONTROLADO = "ERROR_NO_CONTROLADO"


def error_patch_http(codigo_http: int) -> str:
    """Construye el codigo de error para una respuesta PATCH no exitosa."""
    return f"ERROR_PATCH_HTTP_{codigo_http}"


# ============================================================
# EXPLICACIONES LEGIBLES PARA EL USUARIO
# ============================================================

EXPLICACIONES = {
    ERROR_RECURSO_NO_ENCONTRADO: "No se encontro un archivo confiable en el ZIP.",
    ERROR_RECURSO_DUPLICADO: "Varios archivos del ZIP empataron. No se elige al azar.",
    ERROR_ACTIVIDAD_NO_ENCONTRADA: "La actividad no aparece en PRIZMA.",
    ERROR_ACTIVIDAD_DUPLICADA: "Hay mas de una actividad con ese nombre exacto.",
    ERROR_RECUPERANDO_PAGINA: "Fallo la lectura de una pagina de resultados.",
    ERROR_RECUPERANDO_FILA: "No se pudo identificar la fila de la actividad.",
    ERROR_ABRIENDO_EDICION: "No se pudo abrir la pantalla de edicion.",
    ERROR_CAMPO_RECURSO_NO_ENCONTRADO: "No se identifico el campo Recurso de forma unica.",
    ERROR_DESCRIPCION_CONTENIDO_ADICIONAL: "La descripcion tiene texto legitimo junto al placeholder.",
    ERROR_SET_INPUT_FILES: "Fallo la asignacion del archivo al campo Recurso.",
    ERROR_RECURSO_NO_VISIBLE: "El archivo no quedo visible tras asignarlo.",
    ERROR_BOTON_GUARDAR: "No se encontro el boton Editar de tipo submit.",
    ERROR_CLIC_GUARDAR: "Fallo el clic sobre el boton de guardado.",
    ERROR_PATCH_NO_CONFIRMADO: "PRIZMA no confirmo el guardado dentro del tiempo de espera.",
    ERROR_POST_GUARDADO_LISTADO: "No se pudo volver al listado despues de guardar.",
    ERROR_LOGIN_FALLIDO: "No se pudo iniciar sesion en PRIZMA.",
    ERROR_NAVEGADOR_NO_DISPONIBLE: "Chromium no esta disponible en este entorno.",
    ERROR_NO_CONTROLADO: "Error inesperado.",
}


def explicar(codigo: str) -> str:
    """Devuelve una explicacion legible para un codigo de error."""
    if codigo in EXPLICACIONES:
        return EXPLICACIONES[codigo]
    if codigo.startswith("ERROR_PATCH_HTTP_"):
        return f"PRIZMA respondio con codigo HTTP {codigo.rsplit('_', 1)[-1]}."
    return "Error sin descripcion."
