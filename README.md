# AUTO PRIZMA PRO

Aplicacion web que automatiza el cargue masivo de recursos academicos
(OVI y OVA) en PRIZMA a partir de una matriz Excel y un ZIP de recursos.

Plataforma destino: `https://admin.prizma.site/inicio-sesion`

---

## Que hace

1. Recibe la matriz `.xlsx` y el paquete `.zip` desde el navegador.
2. Detecta programa y curso, y localiza dinamicamente la cabecera
   "Semana correspondiente".
3. Filtra las actividades: solo OVI y OVA.
4. Indexa el ZIP una sola vez y asigna cada actividad a un archivo.
5. Muestra un resumen para que la persona confirme antes de tocar PRIZMA.
6. Carga cada recurso, guarda, y confirma con la peticion PATCH.
7. Entrega un reporte CSV descargable.

---

## Reglas criticas

- Todos los archivos, H5P y PDF, se cargan **siempre** en el campo **Recurso**.
- El campo **Material descargable** se ignora **siempre**.
- Si el campo Recurso no se identifica de forma unica, no se guarda.
- La actividad se identifica por nombre exacto, semana, unidad, programa y categoria.
- Cero coincidencias o mas de una: se registra error y se continua.
- `NO_DISPONIBLE` se borra solo si es el unico contenido de la descripcion.
- Despues de guardar **no** se reabre la actividad.
- Un error en una actividad no detiene el curso.

Categorias que **no** se procesan y **no** se modifican:
Challenge, Retos Evaluativos, Video Intro, Video Cierre, Video a camara.

---

## Estructura

```
auto_prizma_pro/
├── aplicacion.py              FastAPI: rutas y arranque
├── configuracion.py           Rutas, constantes y variables de entorno
│
├── nucleo/
│   ├── errores.py             Codigos ERROR_* centralizados
│   ├── registro.py            Log en espanol con filtro de credenciales
│   ├── lector_excel.py        Lectura de la matriz
│   ├── gestor_recursos.py     Indice del ZIP, puntuacion y extraccion
│   ├── gestor_trabajos.py     Trabajos, progreso y reporte CSV
│   └── motor_prizma.py        Playwright
│
├── herramientas/
│   └── inspector_login.py     Inspecciona el login sin enviar credenciales
│
├── plantillas/                inicio, analisis, proceso
├── estaticos/                 estilos.css y aplicacion.js
├── almacenamiento/            cargas, temporales, resultados
│
├── requirements.txt
├── Dockerfile
├── railway.json
├── .env.ejemplo
└── .gitignore
```

---

## Instalacion local en Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Si PowerShell bloquea la activacion:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Arrancar:

```powershell
uvicorn aplicacion:app --reload
```

Abrir `http://127.0.0.1:8000`

---

## Inspeccionar el login antes de automatizarlo

Abre Chromium, describe el formulario real y avisa si hay captcha.
No envia credenciales.

```powershell
python herramientas\inspector_login.py
```

Ejecuta esto **antes** de confiar en el login automatico.
Si aparece reCAPTCHA o inicio de sesion federado, el login remoto
no sera viable con esa cuenta y habra que revisar el enfoque.

---

## Despliegue en Railway

1. Sube el repositorio a GitHub en modo privado.
2. En Railway: **New Project → Deploy from GitHub repo**.
3. Railway detecta el `Dockerfile` automaticamente.
4. Variables de entorno del servicio:

   | Variable | Valor |
   |---|---|
   | `MODO_SERVIDOR` | `true` |
   | `URL_PRIZMA` | `https://admin.prizma.site/inicio-sesion` |

   `PORT` la inyecta Railway. No la definas a mano.

5. Start command, si Railway pide uno:

```
/bin/sh -c "exec uvicorn aplicacion:app --host 0.0.0.0 --port $PORT"
```

---

## Chromium en Railway

El error `Executable doesn't exist at /root/.cache/ms-playwright/...`
aparece cuando la version de playwright de pip no coincide con el
navegador instalado en la imagen.

Este proyecto lo evita asi:

- Imagen base limpia: `python:3.12-bookworm`, sin navegador preinstalado.
- `playwright==1.62.0` fijado en `requirements.txt`.
- `playwright install --with-deps chromium` se ejecuta **despues** de
  `pip install`, por lo que descarga exactamente el Chromium que esa
  version necesita.
- `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright` deja el navegador en una
  ruta fija, fuera del home del usuario.

Si actualizas `playwright` en `requirements.txt`, reconstruye la imagen
para que descargue el navegador correspondiente.

---

## Credenciales

Cada persona escribe su usuario y contrasena de PRIZMA en la pantalla
de confirmacion. Esas credenciales:

- viven solo en la memoria del proceso durante esa ejecucion;
- no se escriben en disco;
- no aparecen en los logs, hay un filtro que las oculta;
- desaparecen al terminar el cargue.

No hay contrasenas en el codigo ni en el repositorio.

---

## Codigos de error del reporte

| Codigo | Que ocurrio |
|---|---|
| `ERROR_RECURSO_NO_ENCONTRADO` | Ningun archivo del ZIP alcanzo el umbral de confianza |
| `ERROR_RECURSO_DUPLICADO` | Varios archivos empataron. No se elige al azar |
| `ERROR_ACTIVIDAD_NO_ENCONTRADA` | La actividad no aparece en PRIZMA |
| `ERROR_ACTIVIDAD_DUPLICADA` | Mas de una coincidencia exacta |
| `ERROR_RECUPERANDO_PAGINA` | Fallo la lectura de una pagina de resultados |
| `ERROR_RECUPERANDO_FILA` | La fila no tiene los 3 botones esperados |
| `ERROR_ABRIENDO_EDICION` | No se abrio la pantalla de edicion |
| `ERROR_CAMPO_RECURSO_NO_ENCONTRADO` | El campo Recurso no se identifico de forma unica |
| `ERROR_DESCRIPCION_CONTENIDO_ADICIONAL` | El placeholder convive con texto real |
| `ERROR_SET_INPUT_FILES` | Fallo la asignacion del archivo |
| `ERROR_RECURSO_NO_VISIBLE` | El archivo no quedo visible tras asignarlo |
| `ERROR_BOTON_GUARDAR` | No se hallo el boton Editar de tipo submit |
| `ERROR_CLIC_GUARDAR` | Fallo el clic de guardado |
| `ERROR_PATCH_NO_CONFIRMADO` | PRIZMA no envio PATCH en 15 segundos |
| `ERROR_PATCH_HTTP_XXX` | PRIZMA respondio con un codigo distinto de 2xx |
| `ERROR_POST_GUARDADO_LISTADO` | El buscador no volvio tras guardar |
| `ERROR_NO_CONTROLADO` | Fallo inesperado |

---

## Rutas de la aplicacion

| Metodo | Ruta | Para que |
|---|---|---|
| GET | `/` | Pantalla inicial |
| POST | `/analizar` | Sube archivos y analiza |
| GET | `/analisis/{id}` | Pantalla de confirmacion |
| POST | `/iniciar/{id}` | Arranca el cargue |
| GET | `/proceso/{id}` | Pantalla de progreso |
| GET | `/estado/{id}` | Estado en vivo, JSON |
| GET | `/reporte/{id}` | Descarga el CSV |
| POST | `/limpiar/{id}` | Borra los archivos del trabajo |
| GET | `/salud` | Estado del servicio |

---

## Orden de trabajo recomendado

1. Instalar en local y abrir la pantalla inicial.
2. Ejecutar `inspector_login.py` y revisar el formulario real.
3. Ajustar los selectores de login en `nucleo/motor_prizma.py`
   con lo que devuelva el inspector.
4. Probar el cargue con **una sola** actividad.
5. Probar un curso completo en local.
6. Construir la imagen Docker.
7. Desplegar en Railway.
8. Probar con un companero desde otro computador.
