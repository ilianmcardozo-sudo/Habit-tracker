"""
Pronunciador: selecciona texto en pantalla y aprende a pronunciarlo.

Flujo:
  1. Presionas el atajo (por defecto Ctrl + Alt + P).
  2. La pantalla se congela y se oscurece, como con Win + Shift + S.
  3. Dibujas una caja sobre la palabra o frase en inglés (Esc para cancelar).
  4. El OCR de Windows lee el texto.
  5. Se abren en Brave:
       - YouTube, buscando la PRIMERA palabra dentro del canal configurado
         (versión American English).
       - Google, con "how to pronounce <frase> American English".
  6. Aparece una ventana con la explicación de la pronunciación de la FRASE
     COMPLETA, pensada para hispanohablantes (requiere clave de Anthropic).

Solo funciona en Windows 10/11.
"""

import ctypes
import datetime
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import urllib.parse
import webbrowser
from tkinter import scrolledtext

# ---------------------------------------------------------------------------
# CONFIGURACIÓN: cambia lo que quieras aquí
# ---------------------------------------------------------------------------

# Atajo de teclado. Ejemplos: "ctrl+alt+p", "ctrl+shift+y", "f8"
ATAJO = "ctrl+alt+p"

# @ del canal de YouTube. Si al buscar ves "Este canal no existe", abre el
# canal en YouTube, copia lo que aparece después de youtube.com/ (empieza
# con @) y pégalo aquí.
CANAL_YOUTUBE = "@englishwithcollinsdictionary"

# Qué se agrega a la búsqueda en YouTube para quedarse con la versión
# americana (los videos de Collins dicen "...in American English").
# Si no sale nada, es que Collins no tiene esa palabra.
SUFIJO_YOUTUBE = "American English"

# Abrir también la búsqueda de Google
ABRIR_GOOGLE = True

# Modelo que explica la pronunciación usando Claude Code (tu suscripción).
# "sonnet" es rápido y explica muy bien; "opus" es más detallado pero más lento.
MODELO_CLAUDE_CODE = "sonnet"

# Solo se usa si NO tienes Claude Code y pones una clave de API en clave_anthropic.txt
MODELO = "claude-opus-5-5"

# Guardar cada consulta en palabras.txt (lista), historial.md (explicaciones)
# y anki.txt (tarjetas para importar en Anki)
GUARDAR_HISTORIAL = True

# ---------------------------------------------------------------------------

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CLAVE = os.path.join(CARPETA, "clave_anthropic.txt")
ARCHIVO_HISTORIAL = os.path.join(CARPETA, "historial.md")
ARCHIVO_PALABRAS = os.path.join(CARPETA, "palabras.txt")
ARCHIVO_ANKI = os.path.join(CARPETA, "anki.txt")

INSTRUCCIONES_CLAUDE = """Eres un profesor de pronunciación de inglés americano (General American) \
para hispanohablantes. El alumno habla español y quiere imitar los sonidos lo mejor posible.

Responde SIEMPRE en español, en texto plano (sin tablas ni markdown pesado; puedes usar \
guiones y mayúsculas para la sílaba tónica). Sé concreto y breve. Usa esta estructura:

1. TEXTO: la palabra o frase tal como la entendiste (corrige errores obvios del OCR y dilo).
2. IPA (americano): transcripción fonética entre barras.
3. CÓMO SUENA, "a la española": una aproximación escrita con letras del español. Reglas:
   - Usa solo letras normales del español, sin símbolos (ï, ë, ɪ, ə...).
   - La sílaba con acento va en MAYÚSCULAS y con tilde (ej.: "effect" -> e-FÉKT). Esa tilde \
marca el acento del inglés, no sigue la ortografía del español, así que ponla también en \
palabras de una sola sílaba.
   - Si un sonido inglés queda entre dos vocales del español, escribe la que un \
hispanohablante oiría en ESA palabra dicha de forma natural en inglés americano. Decide \
palabra por palabra; no apliques una regla fija.
   - Escribe la pronunciación en el mismo orden que el IPA, sin añadir ni quitar sonidos.
   - En frases, escribe las palabras unidas como se dicen al hablar, siguiendo el IPA de la \
frase completa.
4. SONIDO POR SONIDO: solo los sonidos que NO existen en español o que un hispanohablante \
suele pronunciar mal. Compáralos con el sonido español más cercano.

Precisión fonética:
- Describe la boca y la lengua solo si estás seguro. Si no, omítelo.
- Cuando una regla del inglés americano tenga condiciones (por ejemplo, la t que suena \
como "r" solo entre vocales y antes de una sílaba sin acento), aplícala solo si se cumplen \
en esa palabra.
- Mantén los ejemplos coherentes en toda la respuesta.
5. ERRORES TÍPICOS de hispanohablantes con esta palabra/frase y cómo evitarlos.
6. Si es una frase: cómo se enlazan las palabras al hablar rápido (linking, reducciones, \
schwa, flap T) y qué palabras llevan el acento de la frase.
7. TRUCO para practicar: un ejercicio corto (pares mínimos, repetir algo, etc.).

Si el texto no es inglés o no tiene sentido, dilo y sugiere qué pudo haber querido seleccionar.

Al final, en una línea aparte y sin nada después, escribe exactamente este formato (una sola línea):
ANKI: <IPA americano> | <cómo suena a la española> | <el consejo más importante, en una frase corta>"""


# ---------------------------------------------------------------------------
# Utilidades de Windows
# ---------------------------------------------------------------------------

def activar_dpi():
    """Evita que la selección quede desplazada en pantallas con escala 125 %, 150 %, etc."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def pantalla_virtual():
    """Devuelve (x, y, ancho, alto) del escritorio completo (todos los monitores)."""
    u = ctypes.windll.user32
    return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)


def buscar_brave():
    candidatos = []
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            candidatos.append(os.path.join(base, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"))
    for c in candidatos:
        if os.path.isfile(c):
            return c
    return shutil.which("brave") or shutil.which("brave.exe")


def abrir_en_brave(urls):
    brave = buscar_brave()
    if brave:
        subprocess.Popen([brave, *urls])
    else:
        print("No encontré Brave; uso el navegador predeterminado.")
        for u in urls:
            webbrowser.open_new_tab(u)


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def leer_texto(imagen):
    """Lee el texto de una imagen PIL con el OCR integrado de Windows."""
    import winocr
    from PIL import Image, ImageOps

    # Agrandar mejora mucho el OCR en textos pequeños (subtítulos, etc.)
    escala = 3 if imagen.height < 120 else 2 if imagen.height < 300 else 1
    if escala > 1:
        imagen = imagen.resize((imagen.width * escala, imagen.height * escala), Image.LANCZOS)
    # Margen blanco alrededor: ayuda cuando la caja corta justo las letras
    imagen = ImageOps.expand(imagen.convert("RGB"), border=20, fill="white")

    ultimo_error = None
    for idioma in ("en-US", "en-GB", "en", "es-MX", "es-ES", "es"):
        try:
            resultado = winocr.recognize_pil_sync(imagen, idioma)
        except AssertionError as e:  # idioma no instalado en Windows
            ultimo_error = e
            continue
        texto = resultado.get("text", "") if isinstance(resultado, dict) else ""
        return texto
    raise RuntimeError(
        "Windows no tiene ningún idioma de OCR instalado (inglés o español).\n"
        "Ve a Configuración > Hora e idioma > Idioma > Agregar un idioma > English (United States).\n"
        f"Detalle: {ultimo_error}"
    )


def limpiar(texto):
    texto = texto.replace("’", "'").replace("‘", "'")
    texto = re.sub(r"[^A-Za-z'\- ]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" '-")
    return texto


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------

def leer_clave():
    clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not clave and os.path.isfile(ARCHIVO_CLAVE):
        with open(ARCHIVO_CLAVE, encoding="utf-8") as f:
            clave = f.read().strip()
    return clave or None


def buscar_claude_code():
    ruta = shutil.which("claude")
    if ruta:
        return ruta
    for c in (
        os.path.expanduser(r"~\.local\bin\claude.exe"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
    ):
        if os.path.isfile(c):
            return c
    return None


def explicar_con_claude_code(claude, frase):
    """Usa Claude Code instalado en la PC, con la sesión de tu suscripción de Claude."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        archivo_instrucciones = os.path.join(tmp, "instrucciones.txt")
        with open(archivo_instrucciones, "w", encoding="utf-8") as f:
            f.write(INSTRUCCIONES_CLAUDE)

        entorno = dict(os.environ)
        # Si hubiera una clave de API en el sistema, Claude Code la usaría y cobraría
        # aparte. La quitamos para que use siempre tu suscripción.
        entorno.pop("ANTHROPIC_API_KEY", None)

        resultado = subprocess.run(
            [
                claude, "-p",
                "--model", MODELO_CLAUDE_CODE,
                "--tools", "",
                "--no-session-persistence",
                "--system-prompt-file", archivo_instrucciones,
            ],
            input=f'Texto seleccionado en pantalla: "{frase}"',
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=tmp, env=entorno, timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout).strip()
        return (
            "Claude Code dio un error.\n\n"
            "Si dice que no has iniciado sesión: abre una ventana de cmd, escribe  claude  "
            "y sigue los pasos para entrar con tu cuenta de Claude.\n\n"
            f"Detalle: {detalle}"
        )
    return resultado.stdout.strip() or "(Respuesta vacía, inténtalo de nuevo.)"


def explicar_pronunciacion(frase):
    claude = buscar_claude_code()
    if claude:
        return explicar_con_claude_code(claude, frase)

    clave = leer_clave()
    if not clave:
        return (
            "No encontré Claude Code en esta PC, así que no puedo darte la explicación.\n\n"
            "Para instalarlo, abre PowerShell y pega:\n"
            "    irm https://claude.ai/install.ps1 | iex\n"
            "Después abre una ventana de cmd, escribe  claude  e inicia sesión con tu cuenta.\n"
            "Luego cierra y vuelve a abrir iniciar.bat."
        )

    import anthropic

    client = anthropic.Anthropic(api_key=clave)
    peticion = dict(
        model=MODELO,
        max_tokens=4000,
        system=INSTRUCCIONES_CLAUDE,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": f'Texto seleccionado en pantalla: "{frase}"'}],
    )
    try:
        # Si el filtro de seguridad rechaza algo por error, el servidor reintenta con otro modelo.
        respuesta = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **peticion
        )
    except (TypeError, anthropic.BadRequestError):
        # SDK antiguo o función no disponible: petición normal
        respuesta = client.messages.create(**peticion)

    if respuesta.stop_reason == "refusal":
        return "Claude no pudo responder a este texto. Prueba seleccionando solo la palabra."
    texto = "".join(b.text for b in respuesta.content if b.type == "text").strip()
    return texto or "(Respuesta vacía, inténtalo de nuevo.)"


# ---------------------------------------------------------------------------
# Historial y Anki
# ---------------------------------------------------------------------------

def separar_linea_anki(explicacion):
    """Quita la línea 'ANKI: ...' del texto y devuelve (texto_limpio, [ipa, aprox, consejo] o None)."""
    lineas = explicacion.rstrip().splitlines()
    for i in range(len(lineas) - 1, -1, -1):
        linea = lineas[i].strip().strip("*`").strip()
        if linea.upper().startswith("ANKI:"):
            partes = [x.strip() for x in linea[5:].split("|")]
            partes = (partes + ["", "", ""])[:3]
            limpio = "\n".join(lineas[:i] + lineas[i + 1:]).strip()
            return limpio, partes
    return explicacion, None


def _html(texto):
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return texto.replace("\t", " ").replace("\r", "").replace("\n", "<br>")


def guardar_en_registros(frase, explicacion, datos_anki):
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Lista simple de palabras
    with open(ARCHIVO_PALABRAS, "a", encoding="utf-8") as f:
        f.write(f"{fecha}\t{frase}\n")

    # Historial completo
    with open(ARCHIVO_HISTORIAL, "a", encoding="utf-8") as f:
        f.write(f"\n## {frase}  ({fecha})\n\n{explicacion}\n")

    # Tarjetas para Anki (sin repetir palabras)
    if not datos_anki:
        return
    nuevo = not os.path.isfile(ARCHIVO_ANKI)
    if not nuevo:
        with open(ARCHIVO_ANKI, encoding="utf-8") as f:
            ya = {l.split("\t", 1)[0].strip().lower() for l in f if l.strip() and not l.startswith("#")}
        if _html(frase).lower() in ya:
            return
    ipa, aprox, consejo = datos_anki
    reverso = f"<b>{_html(ipa)}</b><br>{_html(aprox)}<br><br><i>{_html(consejo)}</i>"
    with open(ARCHIVO_ANKI, "a", encoding="utf-8") as f:
        if nuevo:
            f.write("#separator:tab\n#html:true\n#columns:Frente\tReverso\tExplicación\n")
        f.write(f"{_html(frase)}\t{reverso}\t{_html(explicacion)}\n")


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------

class Selector:
    """Pantalla congelada y oscurecida donde se dibuja la caja (como Win + Shift + S)."""

    def __init__(self, raiz, al_terminar):
        from PIL import Image, ImageEnhance, ImageGrab, ImageTk

        self.al_terminar = al_terminar
        self.vx, self.vy, ancho, alto = pantalla_virtual()
        self.captura = ImageGrab.grab(all_screens=True)
        oscura = ImageEnhance.Brightness(self.captura).enhance(0.45)

        self.ventana = tk.Toplevel(raiz)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self.ventana.geometry(f"{ancho}x{alto}+{self.vx}+{self.vy}")

        self.lienzo = tk.Canvas(self.ventana, width=ancho, height=alto, cursor="cross", highlightthickness=0)
        self.lienzo.pack(fill="both", expand=True)
        self._fondo = ImageTk.PhotoImage(oscura)
        self.lienzo.create_image(0, 0, anchor="nw", image=self._fondo)
        self.lienzo.create_text(
            ancho // 2, 30, fill="white", font=("Segoe UI", 14),
            text="Dibuja una caja sobre el texto en inglés  ·  Esc para cancelar",
        )

        self._ImageTk = ImageTk
        self.inicio = None
        self.rect = None
        self.recorte_visible = None

        self.lienzo.bind("<ButtonPress-1>", self._presionar)
        self.lienzo.bind("<B1-Motion>", self._arrastrar)
        self.lienzo.bind("<ButtonRelease-1>", self._soltar)
        self.ventana.bind("<Escape>", lambda e: self._cerrar(None))
        self.ventana.focus_force()
        self.ventana.after(50, self.ventana.focus_force)

    def _presionar(self, e):
        self.inicio = (e.x, e.y)

    def _arrastrar(self, e):
        if not self.inicio:
            return
        x0, y0 = self.inicio
        izq, arr, der, aba = min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)
        # Zona seleccionada con brillo normal
        if der - izq > 1 and aba - arr > 1:
            self._recorte_img = self._ImageTk.PhotoImage(self.captura.crop((izq, arr, der, aba)))
            if self.recorte_visible:
                self.lienzo.delete(self.recorte_visible)
            self.recorte_visible = self.lienzo.create_image(izq, arr, anchor="nw", image=self._recorte_img)
        if self.rect:
            self.lienzo.delete(self.rect)
        self.rect = self.lienzo.create_rectangle(izq, arr, der, aba, outline="#4da3ff", width=2)

    def _soltar(self, e):
        if not self.inicio:
            return
        x0, y0 = self.inicio
        caja = (min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y))
        if caja[2] - caja[0] < 5 or caja[3] - caja[1] < 5:
            self._cerrar(None)
            return
        self._cerrar(self.captura.crop(caja))

    def _cerrar(self, recorte):
        self.ventana.destroy()
        self.al_terminar(recorte)


class VentanaPronunciacion:
    def __init__(self, raiz, frase):
        self.v = tk.Toplevel(raiz)
        self.v.title(f"Pronunciación: {frase}")
        self.v.attributes("-topmost", True)
        self.v.geometry("640x620")
        self.v.configure(bg="#1e1e1e")

        tk.Label(
            self.v, text=frase, font=("Segoe UI", 20, "bold"),
            fg="white", bg="#1e1e1e", wraplength=600, justify="left",
        ).pack(anchor="w", padx=16, pady=(14, 4))

        self.caja = scrolledtext.ScrolledText(
            self.v, wrap="word", font=("Segoe UI", 12), bg="#2b2b2b", fg="#eaeaea",
            insertbackground="white", relief="flat", padx=12, pady=10,
        )
        self.caja.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.caja.insert("end", "Preparando la explicación…")
        self.caja.configure(state="disabled")
        self.v.bind("<Escape>", lambda e: self.v.destroy())
        self.v.after(300, lambda: self.v.attributes("-topmost", False))

    def mostrar(self, texto):
        if not self.v.winfo_exists():
            return
        self.caja.configure(state="normal")
        self.caja.delete("1.0", "end")
        self.caja.insert("end", texto)
        self.caja.configure(state="disabled")


class App:
    def __init__(self):
        activar_dpi()
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.eventos = queue.Queue()
        self.ocupado = False
        self.raiz.after(100, self._revisar_eventos)

    def _revisar_eventos(self):
        try:
            while True:
                accion, *datos = self.eventos.get_nowait()
                if accion == "seleccionar" and not self.ocupado:
                    self.ocupado = True
                    Selector(self.raiz, self._procesar)
                elif accion == "explicacion":
                    ventana, texto = datos
                    ventana.mostrar(texto)
        except queue.Empty:
            pass
        self.raiz.after(100, self._revisar_eventos)

    def _procesar(self, recorte):
        self.ocupado = False
        if recorte is None:
            return
        try:
            texto = limpiar(leer_texto(recorte))
        except Exception as e:
            v = VentanaPronunciacion(self.raiz, "Error de OCR")
            v.mostrar(str(e))
            return

        if not texto:
            v = VentanaPronunciacion(self.raiz, "No leí texto")
            v.mostrar("No pude reconocer texto en inglés en esa zona. Prueba con una caja un poco más grande.")
            return

        primera = texto.split(" ")[0]
        print(f"Leído: {texto!r}  ->  YouTube: {primera!r}")

        urls = [
            f"https://www.youtube.com/{CANAL_YOUTUBE}/search?query="
            + urllib.parse.quote(f"{primera} {SUFIJO_YOUTUBE}".strip())
        ]
        if ABRIR_GOOGLE:
            urls.append(
                "https://www.google.com/search?q="
                + urllib.parse.quote(f"how to pronounce {texto} American English")
            )
        abrir_en_brave(urls)

        ventana = VentanaPronunciacion(self.raiz, texto)

        def trabajo():
            ok = True
            try:
                explicacion = explicar_pronunciacion(texto)
            except Exception as e:
                ok = False
                explicacion = f"No pude obtener la explicación de Claude:\n{e}"
            explicacion, datos_anki = separar_linea_anki(explicacion)
            self.eventos.put(("explicacion", ventana, explicacion))
            if GUARDAR_HISTORIAL:
                try:
                    guardar_en_registros(texto, explicacion, datos_anki if ok else None)
                except OSError as e:
                    print(f"No pude guardar el historial: {e}")

        threading.Thread(target=trabajo, daemon=True).start()

    def iniciar(self):
        import keyboard

        keyboard.add_hotkey(ATAJO, lambda: self.eventos.put(("seleccionar",)))
        print(f"Listo. Presiona {ATAJO.upper()} para seleccionar texto. Cierra esta ventana para salir.")
        self.raiz.mainloop()


if __name__ == "__main__":
    if sys.platform != "win32":
        sys.exit("Este script solo funciona en Windows.")
    App().iniciar()
