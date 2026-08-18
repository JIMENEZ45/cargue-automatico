"""
============================================================
REGISTRO DE EVENTOS
============================================================

Mensajes de consola en espanol. Nunca se registran
credenciales: existe un filtro que las oculta.
"""

import logging
import re
import sys

# ============================================================
# FILTRO DE SEGURIDAD
# ============================================================

PATRONES_SENSIBLES = [
    re.compile(r"(contrasena|contraseña|password|clave|token|secret)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(Bearer|Basic)\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
]


class FiltroCredenciales(logging.Filter):
    """Reemplaza cualquier credencial detectada antes de escribir el log."""

    def filter(self, registro: logging.LogRecord) -> bool:
        try:
            mensaje = registro.getMessage()
        except Exception:
            return True
        limpio = mensaje
        for patron in PATRONES_SENSIBLES:
            limpio = patron.sub("[OCULTO]", limpio)
        if limpio != mensaje:
            registro.msg = limpio
            registro.args = ()
        return True


# ============================================================
# CONFIGURACION
# ============================================================

_configurado = False


def configurar_registro(nivel: int = logging.INFO):
    """Prepara el registro global una sola vez."""
    global _configurado
    if _configurado:
        return

    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-7s  %(name)-18s  %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    manejador.addFilter(FiltroCredenciales())

    raiz = logging.getLogger("prizma")
    raiz.setLevel(nivel)
    raiz.handlers.clear()
    raiz.addHandler(manejador)
    raiz.propagate = False

    _configurado = True


def obtener_registro(nombre: str) -> logging.Logger:
    """Devuelve un registro con nombre para un modulo."""
    configurar_registro()
    return logging.getLogger(f"prizma.{nombre}")
