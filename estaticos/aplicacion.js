/* ============================================================
   AUTO PRIZMA PRO - FUNCIONES COMPARTIDAS
   ============================================================ */

/**
 * Muestra el nombre del archivo elegido dentro de su zona.
 */
function enlazarCampoArchivo(idEntrada, idTexto, idZona) {
    const entrada = document.getElementById(idEntrada);
    const texto = document.getElementById(idTexto);
    const zona = document.getElementById(idZona);

    if (!entrada || !texto || !zona) { return; }

    entrada.addEventListener('change', function () {
        if (entrada.files.length > 0) {
            texto.textContent = entrada.files[0].name;
            zona.classList.add('cargado');
        } else {
            zona.classList.remove('cargado');
        }
    });
}

/**
 * Devuelve las categorias marcadas por el usuario.
 */
function leerCategoriasSeleccionadas() {
    const casillas = document.querySelectorAll('.casilla-categoria');
    const marcadas = [];
    casillas.forEach(function (casilla) {
        if (casilla.checked) { marcadas.push(casilla.value); }
    });
    return marcadas;
}

/**
 * Muestra un mensaje de error y lleva la vista hasta el.
 */
function mostrarError(elemento, mensaje) {
    if (!elemento) { return; }
    elemento.textContent = mensaje;
    elemento.classList.remove('oculto');
    elemento.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function ocultarError(elemento) {
    if (!elemento) { return; }
    elemento.classList.add('oculto');
    elemento.textContent = '';
}

/**
 * Bloquea un boton mientras se espera al servidor.
 */
function activarCargando(boton, mensaje) {
    if (!boton) { return; }
    boton.disabled = true;
    boton.innerHTML = '<span class="cargador"></span>' + mensaje;
}

function desactivarCargando(boton, mensaje) {
    if (!boton) { return; }
    boton.disabled = false;
    boton.textContent = mensaje;
}
