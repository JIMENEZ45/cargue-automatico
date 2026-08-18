"""
============================================================
GESTOR DE TRABAJOS
============================================================

Cada ejecucion es un trabajo con identificador unico y
carpetas propias. Aqui vive el estado en vivo que consulta
la interfaz y la generacion del reporte CSV.
"""

import csv
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import configuracion as cfg
from nucleo.registro import obtener_registro

log = obtener_registro("gestor_trabajos")


# ============================================================
# ESTADOS POSIBLES
# ============================================================

ESTADO_CREADO = "creado"
ESTADO_ANALIZADO = "analizado"
ESTADO_EN_PROCESO = "en_proceso"
ESTADO_TERMINADO = "terminado"
ESTADO_FALLIDO = "fallido"


# ============================================================
# TRABAJO
# ============================================================

@dataclass
class Trabajo:
    """Una ejecucion completa de cargue."""

    id_trabajo: str
    creado_en: str

    estado: str = ESTADO_CREADO
    mensaje: str = "Trabajo creado"

    # Archivos de entrada
    ruta_excel: Path = None
    ruta_zip: Path = None

    # Resultado del analisis
    programa: str = ""
    curso: str = ""
    actividades: list = field(default_factory=list)
    categorias_seleccionadas: list = field(default_factory=list)
    omitidas: int = 0
    h5p_en_zip: int = 0
    pdf_en_zip: int = 0

    # Progreso
    total: int = 0
    procesadas: int = 0
    exitosas: int = 0
    con_error: int = 0
    actividad_actual: str = ""

    # Salida
    ruta_reporte: Path = None
    filas_reporte: list = field(default_factory=list)

    _candado: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # --------------------------------------------------------
    @property
    def carpeta_cargas(self) -> Path:
        return cfg.CARPETA_CARGAS / self.id_trabajo

    @property
    def carpeta_temporales(self) -> Path:
        return cfg.CARPETA_TEMPORALES / self.id_trabajo

    def carpeta_fila(self, fila_excel: int) -> Path:
        return self.carpeta_temporales / f"fila_{fila_excel}"

    @property
    def porcentaje(self) -> int:
        if self.total == 0:
            return 0
        return int((self.procesadas / self.total) * 100)

    # --------------------------------------------------------
    def actualizar_progreso(self, actividad_actual: str = None, exito: bool = None):
        """Avanza el contador de forma segura entre hilos."""
        with self._candado:
            if actividad_actual is not None:
                self.actividad_actual = actividad_actual
            if exito is not None:
                self.procesadas += 1
                if exito:
                    self.exitosas += 1
                else:
                    self.con_error += 1

    def registrar_fila_reporte(self, fila: dict):
        with self._candado:
            self.filas_reporte.append(fila)

    # --------------------------------------------------------
    def estado_publico(self) -> dict:
        """Datos que la interfaz consulta durante el proceso."""
        return {
            "id_trabajo": self.id_trabajo,
            "estado": self.estado,
            "mensaje": self.mensaje,
            "programa": self.programa,
            "curso": self.curso,
            "total": self.total,
            "procesadas": self.procesadas,
            "exitosas": self.exitosas,
            "errores": self.con_error,
            "porcentaje": self.porcentaje,
            "actividad_actual": self.actividad_actual,
            "reporte_disponible": bool(self.ruta_reporte and Path(self.ruta_reporte).exists()),
        }

    def resumen_analisis(self) -> dict:
        """Datos que se muestran en la pantalla de confirmacion."""
        h5p_esperados = sum(1 for a in self.actividades if a.extension_esperada == ".h5p")
        pdf_esperados = sum(1 for a in self.actividades if a.extension_esperada == ".pdf")
        ovi = sum(1 for a in self.actividades if a.categoria == "OVI")
        ova = sum(1 for a in self.actividades if a.categoria == "OVA")

        return {
            "id_trabajo": self.id_trabajo,
            "programa": self.programa,
            "curso": self.curso,
            "cantidad_ovi": ovi,
            "cantidad_ova": ova,
            "h5p_esperados": h5p_esperados,
            "pdf_esperados": pdf_esperados,
            "h5p_en_zip": self.h5p_en_zip,
            "pdf_en_zip": self.pdf_en_zip,
            "total_recursos": self.h5p_en_zip + self.pdf_en_zip,
            "omitidas": self.omitidas,
            "total_actividades": len(self.actividades),
            "actividades": [a.a_diccionario() for a in self.actividades],
        }


# ============================================================
# ALMACEN EN MEMORIA
# ============================================================

class AlmacenTrabajos:
    """Guarda los trabajos vivos de esta instancia de la aplicacion."""

    def __init__(self):
        self._trabajos = {}
        self._candado = threading.Lock()

    def crear_trabajo(self) -> Trabajo:
        id_trabajo = uuid.uuid4().hex[:12]
        trabajo = Trabajo(
            id_trabajo=id_trabajo,
            creado_en=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        trabajo.carpeta_cargas.mkdir(parents=True, exist_ok=True)
        trabajo.carpeta_temporales.mkdir(parents=True, exist_ok=True)

        with self._candado:
            self._trabajos[id_trabajo] = trabajo

        log.info("Trabajo creado: %s", id_trabajo)
        return trabajo

    def obtener(self, id_trabajo: str):
        with self._candado:
            return self._trabajos.get(id_trabajo)

    def eliminar(self, id_trabajo: str):
        with self._candado:
            self._trabajos.pop(id_trabajo, None)

    def limpiar_archivos(self, id_trabajo: str):
        """Borra archivos temporales de un trabajo terminado."""
        for carpeta in (cfg.CARPETA_TEMPORALES / id_trabajo, cfg.CARPETA_CARGAS / id_trabajo):
            if carpeta.exists():
                shutil.rmtree(carpeta, ignore_errors=True)
        log.info("Archivos del trabajo %s eliminados", id_trabajo)


almacen = AlmacenTrabajos()


# ============================================================
# REPORTE CSV
# ============================================================

def generar_reporte_csv(trabajo: Trabajo) -> Path:
    """Escribe el reporte del trabajo y devuelve su ruta."""
    cfg.CARPETA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    ruta = cfg.CARPETA_RESULTADOS / f"resultado_{trabajo.id_trabajo}.csv"

    with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=cfg.COLUMNAS_REPORTE, delimiter=";")
        escritor.writeheader()
        for fila in trabajo.filas_reporte:
            escritor.writerow({columna: fila.get(columna, "") for columna in cfg.COLUMNAS_REPORTE})

    trabajo.ruta_reporte = ruta
    log.info("Reporte generado: %s (%s filas)", ruta.name, len(trabajo.filas_reporte))
    return ruta


def construir_fila_reporte(actividad, resultado: str, observacion: str) -> dict:
    """Arma una fila del reporte a partir de una actividad."""
    return {
        "Fila Excel": actividad.fila_excel,
        "Programa": actividad.programa,
        "Curso": actividad.curso,
        "Semana": actividad.semana,
        "Unidad": actividad.unidad,
        "Actividad": actividad.nombre,
        "Categoria": actividad.categoria,
        "Tipo": actividad.extension_esperada.replace(".", "").upper(),
        "Recurso": actividad.archivo_asignado,
        "Resultado": resultado,
        "Observacion": observacion,
    }
