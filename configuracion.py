"""
============================================================
AUTO PRIZMA PRO - CONFIGURACION CENTRAL
============================================================

Unico lugar donde se definen rutas, constantes y variables
de entorno. Ningun otro archivo debe construir rutas a mano.
"""

import os
from pathlib import Path

# ============================================================
# IDENTIDAD DE LA APLICACION
# ============================================================

NOMBRE_APLICACION = "Auto Prizma Pro"
VERSION_APLICACION = "1.0.0"

# ============================================================
# RUTAS BASE
# ============================================================

RAIZ_PROYECTO = Path(__file__).resolve().parent

CARPETA_PLANTILLAS = RAIZ_PROYECTO / "plantillas"
CARPETA_ESTATICOS = RAIZ_PROYECTO / "estaticos"

CARPETA_ALMACENAMIENTO = RAIZ_PROYECTO / "almacenamiento"
CARPETA_CARGAS = CARPETA_ALMACENAMIENTO / "cargas"
CARPETA_TEMPORALES = CARPETA_ALMACENAMIENTO / "temporales"
CARPETA_RESULTADOS = CARPETA_ALMACENAMIENTO / "resultados"


def preparar_carpetas():
    """Crea las carpetas de trabajo si todavia no existen."""
    for carpeta in (CARPETA_CARGAS, CARPETA_TEMPORALES, CARPETA_RESULTADOS):
        carpeta.mkdir(parents=True, exist_ok=True)


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================

def _leer_booleano(nombre: str, por_defecto: bool = False) -> bool:
    valor = os.environ.get(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


# true en Railway (sin escritorio) / false en local (Chromium visible)
MODO_SERVIDOR = _leer_booleano("MODO_SERVIDOR", False)

# En servidor el navegador debe ir sin ventana
NAVEGADOR_SIN_VENTANA = MODO_SERVIDOR

PUERTO = int(os.environ.get("PORT", "8000"))

# ============================================================
# PRIZMA
# ============================================================

URL_PRIZMA_LOGIN = os.environ.get(
    "URL_PRIZMA", "https://admin.prizma.site/inicio-sesion"
)
URL_PRIZMA_BASE = "https://admin.prizma.site"

# ============================================================
# CATEGORIAS
# ============================================================

CATEGORIAS_SOPORTADAS = ("OVI", "OVA")

CATEGORIAS_EXCLUIDAS = (
    "CHALLENGE",
    "RETOS EVALUATIVOS",
    "RETO EVALUATIVO",
    "VIDEO INTRO",
    "VIDEO CIERRE",
    "VIDEO A CAMARA",
)

# ============================================================
# EXCEL
# ============================================================

TEXTO_CABECERA_SEMANA = "SEMANA CORRESPONDIENTE"
FILAS_MAXIMAS_BUSQUEDA_CABECERA = 25

COLUMNA_SEMANA = 1        # A
COLUMNA_UNIDAD = 2        # B
COLUMNA_AUXILIAR = 3      # C
COLUMNA_ACTIVIDAD = 4     # D
COLUMNA_CATEGORIA = 5     # E
COLUMNA_TIPO = 6          # F
COLUMNA_REFERENCIA = 7    # G
COLUMNA_ESTADO = 8        # H

FILA_PROGRAMA = 1
FILA_CURSO = 2
FILA_SEMESTRE = 3
FILA_VARIANTE = 4

# ============================================================
# SELECCION DE RECURSOS DENTRO DEL ZIP
# ============================================================

PUNTOS_NOMBRE_EXACTO = 300
PUNTOS_ACTIVIDAD_CONTENIDA = 180
PUNTOS_REFERENCIA_CONTIENE_NOMBRE = 80
PUNTOS_NOMBRE_CONTIENE_REFERENCIA = 120
PUNTOS_MAXIMOS_PALABRAS = 100

UMBRAL_MINIMO_PUNTUACION = 100

EXTENSIONES_H5P = (".h5p",)
EXTENSIONES_PDF = (".pdf",)

PALABRAS_IGNORADAS = {
    "de", "del", "la", "el", "los", "las", "y", "o", "un", "una",
    "en", "para", "por", "con", "al", "a", "que", "se", "su", "sus",
    "ovi", "ova", "h5p", "pdf", "recurso", "actividad",
}

# ============================================================
# DESCRIPCION
# ============================================================

PLACEHOLDERS_DESCRIPCION = ("NO_DISPONIBLE", "NO_DISPOINBLE")

# ============================================================
# TIEMPOS DE ESPERA (milisegundos)
# ============================================================

ESPERA_PATCH_MS = 15000
ESPERA_NAVEGACION_MS = 30000
ESPERA_ELEMENTO_MS = 10000
ESPERA_LOGIN_MANUAL_MS = 300000  # 5 minutos en modo local

# ============================================================
# SELECTORES CONOCIDOS DE PRIZMA
# ============================================================

SELECTOR_BUSCADOR = 'input[placeholder="Buscar..."]'
SELECTOR_OVERLAY_EXITO = "div.MuiBox-root.css-15m6u24"
PATRON_PATCH_ACTIVIDAD = "/academic/activity/"

# ============================================================
# REPORTE CSV
# ============================================================

COLUMNAS_REPORTE = [
    "Fila Excel",
    "Programa",
    "Curso",
    "Semana",
    "Unidad",
    "Actividad",
    "Categoria",
    "Tipo",
    "Recurso",
    "Resultado",
    "Observacion",
]

MENSAJE_EXITO = "Carga guardada - PATCH confirmado"
