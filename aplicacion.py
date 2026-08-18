"""
============================================================
AUTO PRIZMA PRO - APLICACION WEB
============================================================

FastAPI: rutas, subida de archivos, analisis, ejecucion del
cargue en segundo plano y descarga del reporte.

Arranque local:
    uvicorn aplicacion:app --reload

Arranque en Railway:
    uvicorn aplicacion:app --host 0.0.0.0 --port $PORT
"""

import shutil
import threading

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import configuracion as cfg
from nucleo import gestor_trabajos, motor_prizma
from nucleo.gestor_recursos import IndiceRecursos
from nucleo.lector_excel import leer_actividades_excel, normalizar_texto
from nucleo.registro import obtener_registro

log = obtener_registro("aplicacion")

# ============================================================
# ARRANQUE
# ============================================================

cfg.preparar_carpetas()

app = FastAPI(
    title=cfg.NOMBRE_APLICACION,
    version=cfg.VERSION_APLICACION,
    docs_url=None,
    redoc_url=None,
)

app.mount("/estaticos", StaticFiles(directory=str(cfg.CARPETA_ESTATICOS)), name="estaticos")
plantillas = Jinja2Templates(directory=str(cfg.CARPETA_PLANTILLAS))


# ============================================================
# PANTALLA INICIAL
# ============================================================

@app.get("/", response_class=HTMLResponse)
def pantalla_inicio(request: Request):
    return plantillas.TemplateResponse(
        request,
        "inicio.html",
        {
            "nombre_aplicacion": cfg.NOMBRE_APLICACION,
            "version": cfg.VERSION_APLICACION,
            "modo_servidor": cfg.MODO_SERVIDOR,
            "playwright_listo": motor_prizma.playwright_disponible(),
        },
    )


# ============================================================
# ANALISIS DE ARCHIVOS
# ============================================================

@app.post("/analizar")
async def analizar_archivos(
    archivo_excel: UploadFile = File(...),
    archivo_zip: UploadFile = File(...),
    categorias: str = Form("OVI,OVA"),
):
    """Guarda los archivos, lee la matriz e indexa el ZIP."""
    if not archivo_excel.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "El archivo de matriz debe tener extensión .xlsx")
    if not archivo_zip.filename.lower().endswith(".zip"):
        raise HTTPException(400, "El archivo de recursos debe tener extensión .zip")

    seleccionadas = [
        normalizar_texto(c) for c in categorias.split(",") if normalizar_texto(c)
    ]
    seleccionadas = [c for c in seleccionadas if c in cfg.CATEGORIAS_SOPORTADAS]
    if not seleccionadas:
        raise HTTPException(400, "Selecciona al menos una categoría: OVI u OVA")

    trabajo = gestor_trabajos.almacen.crear_trabajo()
    trabajo.categorias_seleccionadas = seleccionadas

    # Guardar entradas
    trabajo.ruta_excel = trabajo.carpeta_cargas / "matriz.xlsx"
    trabajo.ruta_zip = trabajo.carpeta_cargas / "recursos.zip"

    with open(trabajo.ruta_excel, "wb") as destino:
        shutil.copyfileobj(archivo_excel.file, destino)
    with open(trabajo.ruta_zip, "wb") as destino:
        shutil.copyfileobj(archivo_zip.file, destino)

    # Leer matriz
    try:
        lectura = leer_actividades_excel(trabajo.ruta_excel)
    except Exception as fallo:
        gestor_trabajos.almacen.eliminar(trabajo.id_trabajo)
        raise HTTPException(400, f"No se pudo leer la matriz: {fallo}")

    # Indexar ZIP
    try:
        indice = IndiceRecursos(trabajo.ruta_zip)
    except Exception as fallo:
        gestor_trabajos.almacen.eliminar(trabajo.id_trabajo)
        raise HTTPException(400, f"No se pudo leer el ZIP: {fallo}")

    trabajo.programa = lectura.programa
    trabajo.curso = lectura.curso
    trabajo.omitidas = lectura.omitidas
    trabajo.h5p_en_zip = indice.cantidad_h5p
    trabajo.pdf_en_zip = indice.cantidad_pdf
    trabajo.actividades = [
        a for a in lectura.actividades if a.categoria in seleccionadas
    ]
    trabajo.total = len(trabajo.actividades)
    trabajo.estado = gestor_trabajos.ESTADO_ANALIZADO
    trabajo.mensaje = "Analisis completado"

    if not trabajo.actividades:
        raise HTTPException(
            400,
            "La matriz no contiene actividades OVI ni OVA con las categorías seleccionadas.",
        )

    return JSONResponse(trabajo.resumen_analisis())


# ============================================================
# PANTALLA DE CONFIRMACION
# ============================================================

@app.get("/analisis/{id_trabajo}", response_class=HTMLResponse)
def pantalla_analisis(request: Request, id_trabajo: str):
    trabajo = gestor_trabajos.almacen.obtener(id_trabajo)
    if trabajo is None:
        raise HTTPException(404, "El trabajo no existe o ya expiró")

    return plantillas.TemplateResponse(
        request,
        "analisis.html",
        {
            "nombre_aplicacion": cfg.NOMBRE_APLICACION,
            "resumen": trabajo.resumen_analisis(),
            "modo_servidor": cfg.MODO_SERVIDOR,
        },
    )


# ============================================================
# INICIO DEL CARGUE
# ============================================================

@app.post("/iniciar/{id_trabajo}")
def iniciar_cargue(
    id_trabajo: str,
    usuario: str = Form(""),
    contrasena: str = Form(""),
    login_manual: str = Form("false"),
):
    """
    Arranca el cargue en un hilo aparte.
    Las credenciales solo viven en memoria durante esta ejecucion.
    """
    trabajo = gestor_trabajos.almacen.obtener(id_trabajo)
    if trabajo is None:
        raise HTTPException(404, "El trabajo no existe o ya expiró")

    if trabajo.estado == gestor_trabajos.ESTADO_EN_PROCESO:
        raise HTTPException(409, "Este trabajo ya se está ejecutando")

    usar_login_manual = login_manual.lower() in ("true", "1", "si", "on")

    if not usar_login_manual and (not usuario or not contrasena):
        raise HTTPException(400, "Escribe tu usuario y contraseña de PRIZMA")

    if not motor_prizma.playwright_disponible():
        raise HTTPException(
            503,
            "Playwright no está instalado en este entorno. "
            "Ejecuta: pip install playwright && playwright install chromium",
        )

    hilo = threading.Thread(
        target=motor_prizma.ejecutar_cargue,
        args=(trabajo, usuario, contrasena, usar_login_manual),
        daemon=True,
    )
    hilo.start()

    return JSONResponse({"id_trabajo": id_trabajo, "estado": "iniciado"})


# ============================================================
# PANTALLA DE PROGRESO
# ============================================================

@app.get("/proceso/{id_trabajo}", response_class=HTMLResponse)
def pantalla_proceso(request: Request, id_trabajo: str):
    trabajo = gestor_trabajos.almacen.obtener(id_trabajo)
    if trabajo is None:
        raise HTTPException(404, "El trabajo no existe o ya expiró")

    return plantillas.TemplateResponse(
        request,
        "proceso.html",
        {
            "nombre_aplicacion": cfg.NOMBRE_APLICACION,
            "id_trabajo": id_trabajo,
            "curso": trabajo.curso,
            "programa": trabajo.programa,
            "total": trabajo.total,
        },
    )


@app.get("/estado/{id_trabajo}")
def consultar_estado(id_trabajo: str):
    trabajo = gestor_trabajos.almacen.obtener(id_trabajo)
    if trabajo is None:
        raise HTTPException(404, "El trabajo no existe o ya expiró")
    return JSONResponse(trabajo.estado_publico())


# ============================================================
# REPORTE
# ============================================================

@app.get("/reporte/{id_trabajo}")
def descargar_reporte(id_trabajo: str):
    trabajo = gestor_trabajos.almacen.obtener(id_trabajo)
    if trabajo is None:
        raise HTTPException(404, "El trabajo no existe o ya expiró")
    if not trabajo.ruta_reporte or not trabajo.ruta_reporte.exists():
        raise HTTPException(404, "El reporte todavía no está disponible")

    return FileResponse(
        path=str(trabajo.ruta_reporte),
        media_type="text/csv",
        filename=f"reporte_prizma_{id_trabajo}.csv",
    )


# ============================================================
# LIMPIEZA
# ============================================================

@app.post("/limpiar/{id_trabajo}")
def limpiar_trabajo(id_trabajo: str):
    trabajo = gestor_trabajos.almacen.obtener(id_trabajo)
    if trabajo is None:
        raise HTTPException(404, "El trabajo no existe")
    if trabajo.estado == gestor_trabajos.ESTADO_EN_PROCESO:
        raise HTTPException(409, "No se puede limpiar un trabajo en ejecución")

    gestor_trabajos.almacen.limpiar_archivos(id_trabajo)
    gestor_trabajos.almacen.eliminar(id_trabajo)
    return JSONResponse({"estado": "limpiado"})


# ============================================================
# SALUD
# ============================================================

@app.get("/salud")
def revisar_salud():
    return {
        "aplicacion": cfg.NOMBRE_APLICACION,
        "version": cfg.VERSION_APLICACION,
        "modo_servidor": cfg.MODO_SERVIDOR,
        "playwright": motor_prizma.playwright_disponible(),
    }
