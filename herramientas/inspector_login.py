"""
============================================================
INSPECTOR DEL FORMULARIO DE INICIO DE SESION
============================================================

Abre la pantalla de login de PRIZMA y describe el formulario
real: inputs, atributos y botones.

NO envia credenciales. NO pulsa nada. Solo observa.

Uso:
    python herramientas/inspector_login.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import configuracion as cfg  # noqa: E402


def describir_formulario():
    """Imprime la estructura del formulario de inicio de sesion."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright no esta instalado.")
        print("Ejecuta: pip install playwright && playwright install chromium")
        return

    print("=" * 60)
    print("INSPECTOR DE LOGIN - AUTO PRIZMA PRO")
    print("=" * 60)
    print(f"URL: {cfg.URL_PRIZMA_LOGIN}")
    print("No se enviara ninguna credencial.")
    print("=" * 60)

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(headless=cfg.NAVEGADOR_SIN_VENTANA)
        pagina = navegador.new_page(viewport={"width": 1440, "height": 900})

        pagina.goto(cfg.URL_PRIZMA_LOGIN, wait_until="networkidle", timeout=60000)
        pagina.wait_for_timeout(2500)

        print(f"\nTitulo de la pagina: {pagina.title()}")
        print(f"URL final: {pagina.url}\n")

        # ----------------------------------------------------
        # ENTRADAS
        # ----------------------------------------------------
        entradas = pagina.evaluate("""
            () => Array.from(document.querySelectorAll('input')).map((elemento, indice) => ({
                indice: indice,
                type: elemento.type,
                name: elemento.name,
                id: elemento.id,
                placeholder: elemento.placeholder,
                autocomplete: elemento.autocomplete,
                required: elemento.required,
                visible: elemento.offsetParent !== null,
                clases: elemento.className
            }))
        """)

        print("-" * 60)
        print(f"ENTRADAS ENCONTRADAS: {len(entradas)}")
        print("-" * 60)
        for entrada in entradas:
            print(json.dumps(entrada, indent=2, ensure_ascii=False))

        # ----------------------------------------------------
        # BOTONES
        # ----------------------------------------------------
        botones = pagina.evaluate("""
            () => Array.from(document.querySelectorAll('button, input[type=submit]')).map((elemento, indice) => ({
                indice: indice,
                type: elemento.type,
                texto: (elemento.innerText || elemento.value || '').trim(),
                visible: elemento.offsetParent !== null,
                clases: elemento.className
            }))
        """)

        print("-" * 60)
        print(f"BOTONES ENCONTRADOS: {len(botones)}")
        print("-" * 60)
        for boton in botones:
            print(json.dumps(boton, indent=2, ensure_ascii=False))

        # ----------------------------------------------------
        # FORMULARIOS
        # ----------------------------------------------------
        formularios = pagina.evaluate("""
            () => Array.from(document.querySelectorAll('form')).map((elemento, indice) => ({
                indice: indice,
                action: elemento.action,
                method: elemento.method,
                entradas: elemento.querySelectorAll('input').length
            }))
        """)

        print("-" * 60)
        print(f"FORMULARIOS ENCONTRADOS: {len(formularios)}")
        print("-" * 60)
        for formulario in formularios:
            print(json.dumps(formulario, indent=2, ensure_ascii=False))

        # ----------------------------------------------------
        # SENALES DE PROTECCION
        # ----------------------------------------------------
        senales = pagina.evaluate("""
            () => ({
                recaptcha: !!document.querySelector('.g-recaptcha, iframe[src*=recaptcha]'),
                hcaptcha: !!document.querySelector('.h-captcha, iframe[src*=hcaptcha]'),
                turnstile: !!document.querySelector('iframe[src*=turnstile]'),
                oauth: /google|microsoft|sso|saml/i.test(document.body.innerText)
            })
        """)

        print("-" * 60)
        print("PROTECCIONES DETECTADAS")
        print("-" * 60)
        print(json.dumps(senales, indent=2, ensure_ascii=False))

        if any(senales.values()):
            print("\nATENCION: hay proteccion contra automatizacion.")
            print("El login automatico puede no ser viable con esta cuenta.")
        else:
            print("\nNo se detectaron captchas ni inicio de sesion federado.")

        # ----------------------------------------------------
        # CAPTURA
        # ----------------------------------------------------
        destino = Path(__file__).resolve().parent.parent / "almacenamiento" / "login_prizma.png"
        pagina.screenshot(path=str(destino))
        print(f"\nCaptura guardada en: {destino}")

        if not cfg.NAVEGADOR_SIN_VENTANA:
            print("\nLa ventana se cerrara en 20 segundos.")
            pagina.wait_for_timeout(20000)

        navegador.close()

    print("\nInspeccion terminada.")


if __name__ == "__main__":
    describir_formulario()
