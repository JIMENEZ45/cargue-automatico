# ============================================================
# AUTO PRIZMA PRO - IMAGEN DE PRODUCCION
# ============================================================
# Estrategia: la MISMA version de playwright instalada por pip
# descarga su propio Chromium. Asi no hay desajuste entre la
# libreria de Python y el navegador.
# ============================================================

FROM python:3.12-bookworm

# El navegador se instala en una ruta fija y accesible
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODO_SERVIDOR=true

WORKDIR /aplicacion

# ------------------------------------------------------------
# DEPENDENCIAS DE PYTHON
# ------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------
# CHROMIUM Y SUS LIBRERIAS DE SISTEMA
# ------------------------------------------------------------
RUN playwright install --with-deps chromium

# ------------------------------------------------------------
# CODIGO DE LA APLICACION
# ------------------------------------------------------------
COPY . .

RUN mkdir -p almacenamiento/cargas almacenamiento/temporales almacenamiento/resultados

EXPOSE 8000

CMD ["/bin/sh", "-c", "exec uvicorn aplicacion:app --host 0.0.0.0 --port ${PORT:-8000}"]
