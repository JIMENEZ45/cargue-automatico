"""
============================================================
GESTOR DE RECURSOS DEL ZIP
============================================================

Construye UNA sola vez el indice del ZIP, asigna cada
actividad a un archivo mediante puntuacion, y extrae
unicamente el archivo elegido.

La prioridad es la SEGURIDAD: ante empate o baja
confianza no se elige nada.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path

import configuracion as cfg
from nucleo import errores
from nucleo.lector_excel import normalizar_texto
from nucleo.registro import obtener_registro

log = obtener_registro("gestor_recursos")


# ============================================================
# ENTRADA DEL INDICE
# ============================================================

@dataclass
class RecursoZip:
    """Un archivo util encontrado dentro del ZIP."""

    ruta_interna: str      # ruta completa dentro del ZIP
    nombre_archivo: str    # solo el nombre con extension
    nombre_sin_extension: str
    extension: str

    @property
    def nombre_normalizado(self) -> str:
        return normalizar_texto(self.nombre_sin_extension)


# ============================================================
# INDICE
# ============================================================

class IndiceRecursos:
    """Indice en memoria de los H5P y PDF contenidos en el ZIP."""

    def __init__(self, ruta_zip: Path):
        self.ruta_zip = Path(ruta_zip)
        self.recursos: list = []
        self._construir_indice()

    # --------------------------------------------------------
    def _construir_indice(self):
        if not self.ruta_zip.exists():
            raise FileNotFoundError(f"No existe el ZIP: {self.ruta_zip}")

        extensiones_validas = cfg.EXTENSIONES_H5P + cfg.EXTENSIONES_PDF

        with zipfile.ZipFile(self.ruta_zip, "r") as archivo_zip:
            for informacion in archivo_zip.infolist():
                if informacion.is_dir():
                    continue

                ruta_interna = informacion.filename
                nombre_archivo = Path(ruta_interna).name

                # Ignorar basura de macOS y archivos ocultos
                if nombre_archivo.startswith(".") or "__MACOSX" in ruta_interna:
                    continue

                extension = Path(nombre_archivo).suffix.lower()
                if extension not in extensiones_validas:
                    continue

                self.recursos.append(
                    RecursoZip(
                        ruta_interna=ruta_interna,
                        nombre_archivo=nombre_archivo,
                        nombre_sin_extension=Path(nombre_archivo).stem,
                        extension=extension,
                    )
                )

        log.info(
            "Indice del ZIP construido: %s H5P, %s PDF",
            self.cantidad_h5p,
            self.cantidad_pdf,
        )

    # --------------------------------------------------------
    @property
    def cantidad_h5p(self) -> int:
        return sum(1 for r in self.recursos if r.extension in cfg.EXTENSIONES_H5P)

    @property
    def cantidad_pdf(self) -> int:
        return sum(1 for r in self.recursos if r.extension in cfg.EXTENSIONES_PDF)

    @property
    def total(self) -> int:
        return len(self.recursos)

    def recursos_por_extension(self, extension: str) -> list:
        return [r for r in self.recursos if r.extension == extension.lower()]


# ============================================================
# PUNTUACION
# ============================================================

def _palabras_significativas(texto: str) -> set:
    """Palabras utiles de un texto, sin conectores ni ruido."""
    normalizado = normalizar_texto(texto)
    separadores = "-_.,;:()[]{}/\\"
    for caracter in separadores:
        normalizado = normalizado.replace(caracter, " ")
    palabras = set()
    for palabra in normalizado.split():
        if len(palabra) < 3:
            continue
        if palabra.lower() in cfg.PALABRAS_IGNORADAS:
            continue
        palabras.add(palabra)
    return palabras


def puntuar_recurso(recurso: RecursoZip, nombre_actividad: str, referencia: str) -> int:
    """
    Calcula la confianza de que este archivo corresponda a la actividad.
    Puntuacion validada en pruebas anteriores.
    """
    actividad_norm = normalizar_texto(nombre_actividad)
    referencia_norm = normalizar_texto(referencia)
    archivo_norm = recurso.nombre_normalizado

    if not actividad_norm or not archivo_norm:
        return 0

    puntos = 0

    # Coincidencia perfecta
    if archivo_norm == actividad_norm:
        puntos += cfg.PUNTOS_NOMBRE_EXACTO

    # El nombre de la actividad aparece completo dentro del nombre del archivo
    elif actividad_norm in archivo_norm:
        puntos += cfg.PUNTOS_ACTIVIDAD_CONTENIDA

    # Relacion con la referencia de la matriz
    if referencia_norm:
        if archivo_norm in referencia_norm:
            puntos += cfg.PUNTOS_REFERENCIA_CONTIENE_NOMBRE
        if referencia_norm in archivo_norm:
            puntos += cfg.PUNTOS_NOMBRE_CONTIENE_REFERENCIA

    # Coincidencia de palabras significativas
    palabras_actividad = _palabras_significativas(nombre_actividad)
    palabras_archivo = _palabras_significativas(recurso.nombre_sin_extension)

    if palabras_actividad and palabras_archivo:
        comunes = palabras_actividad & palabras_archivo
        proporcion = len(comunes) / len(palabras_actividad)
        puntos += int(proporcion * cfg.PUNTOS_MAXIMOS_PALABRAS)

    return puntos


# ============================================================
# RESOLUCION
# ============================================================

@dataclass
class ResolucionRecurso:
    """Resultado de intentar asignar un archivo a una actividad."""

    encontrado: bool
    recurso: RecursoZip = None
    puntuacion: int = 0
    codigo_error: str = ""
    detalle: str = ""


def resolver_recurso(indice: IndiceRecursos, nombre_actividad: str,
                     referencia: str, extension_esperada: str) -> ResolucionRecurso:
    """
    Elige el archivo del ZIP que corresponde a una actividad.

    Nunca adivina:
      - empate en la mejor puntuacion -> ERROR_RECURSO_DUPLICADO
      - nada supera el umbral        -> ERROR_RECURSO_NO_ENCONTRADO
    """
    candidatos = indice.recursos_por_extension(extension_esperada)

    if not candidatos:
        return ResolucionRecurso(
            encontrado=False,
            codigo_error=errores.ERROR_RECURSO_NO_ENCONTRADO,
            detalle=f"El ZIP no contiene archivos {extension_esperada}",
        )

    puntuados = []
    for candidato in candidatos:
        puntos = puntuar_recurso(candidato, nombre_actividad, referencia)
        if puntos >= cfg.UMBRAL_MINIMO_PUNTUACION:
            puntuados.append((puntos, candidato))

    if not puntuados:
        return ResolucionRecurso(
            encontrado=False,
            codigo_error=errores.ERROR_RECURSO_NO_ENCONTRADO,
            detalle=f"Ningun archivo alcanzo el umbral de {cfg.UMBRAL_MINIMO_PUNTUACION} puntos",
        )

    mejor_puntuacion = max(puntos for puntos, _ in puntuados)
    empatados = [candidato for puntos, candidato in puntuados if puntos == mejor_puntuacion]

    if len(empatados) > 1:
        nombres = ", ".join(c.nombre_archivo for c in empatados[:4])
        return ResolucionRecurso(
            encontrado=False,
            puntuacion=mejor_puntuacion,
            codigo_error=errores.ERROR_RECURSO_DUPLICADO,
            detalle=f"{len(empatados)} archivos empatados: {nombres}",
        )

    elegido = empatados[0]
    log.info(
        'Recurso asignado a "%s": %s (%s puntos)',
        nombre_actividad, elegido.nombre_archivo, mejor_puntuacion,
    )

    return ResolucionRecurso(
        encontrado=True,
        recurso=elegido,
        puntuacion=mejor_puntuacion,
    )


# ============================================================
# EXTRACCION
# ============================================================

def extraer_recurso(ruta_zip: Path, recurso: RecursoZip, carpeta_destino: Path) -> Path:
    """
    Extrae UNICAMENTE el archivo indicado, conservando su nombre original.
    Devuelve la ruta del archivo en disco.
    """
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)

    ruta_final = carpeta_destino / recurso.nombre_archivo

    with zipfile.ZipFile(ruta_zip, "r") as archivo_zip:
        with archivo_zip.open(recurso.ruta_interna) as origen:
            with open(ruta_final, "wb") as destino:
                destino.write(origen.read())

    log.info("Recurso extraido: %s", ruta_final.name)
    return ruta_final
