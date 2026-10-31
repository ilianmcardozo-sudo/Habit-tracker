# Pronunciador (Windows 10/11)

Presionas **Ctrl + Alt + P**, la pantalla se congela como con `Win + Shift + S`, dibujas una caja sobre una palabra o frase en inglés y:

1. Se abre **Brave** con dos pestañas:
   - **YouTube**: busca la **primera palabra** dentro del canal *English with Collins Dictionary*, versión **American English**.
   - **Google**: `how to pronounce <frase> American English`. Google suele mostrar su widget de pronunciación con audio.
2. Aparece una ventana con la explicación de la **frase completa** para hispanohablantes: IPA americano, cómo suena "a la española", qué hacer con la boca en los sonidos que no existen en español, errores típicos y un ejercicio.
3. Cada consulta se guarda en `historial.md` para repasar.

Sirve con cualquier cosa en pantalla: videos (la imagen se congela al presionar el atajo), PDFs, páginas web o imágenes.

## Instalación (una sola vez)

1. **Instala Python** desde https://www.python.org/downloads/ y marca la casilla **"Add python.exe to PATH"** durante la instalación.
2. Haz doble clic en **`instalar.bat`**.
3. **Claude Code** (para la explicación de pronunciación, usa tu suscripción de Claude, sin pagos extra):
   - Comprueba si lo tienes: abre `cmd` y escribe `claude --version`.
   - Si no lo tienes, abre PowerShell y pega `irm https://claude.ai/install.ps1 | iex`.
   - Abre `cmd`, escribe `claude` e inicia sesión con tu cuenta de Claude (solo la primera vez).
   - Sin Claude Code, las búsquedas de YouTube y Google siguen funcionando.
4. **Idioma de OCR**: normalmente ya está instalado. Si te aparece un error de OCR, ve a *Configuración → Hora e idioma → Idioma → Agregar un idioma → English (United States)*.

## Uso

- Doble clic en **`iniciar.bat`**. Se abre una ventana negra: déjala abierta, porque ahí se ve qué texto leyó el programa.
- Si no quieres ver esa ventana, usa **`iniciar_oculto.bat`**. En ese caso lo cierras desde el Administrador de tareas (proceso `pythonw`).
- **Esc** cancela la selección o cierra la ventana de explicación.

### Que arranque solo al encender la PC

1. Presiona `Win + R`, escribe `shell:startup` y presiona Enter.
2. Arrastra ahí `iniciar_oculto.bat` **con clic derecho** y elige *Crear acceso directo aquí*.

## Ajustes

Al inicio de `pronunciar.py`, en la sección **CONFIGURACIÓN**, puedes cambiar:

| Opción | Qué hace |
|---|---|
| `ATAJO` | La combinación de teclas (`"ctrl+alt+p"`, `"f8"`, …) |
| `CANAL_YOUTUBE` | El @ del canal. **Si YouTube dice que el canal no existe**, abre el canal de Collins, copia lo que va después de `youtube.com/` y pégalo aquí |
| `SUFIJO_YOUTUBE` | Texto extra para la búsqueda en YouTube (vacío = solo la palabra) |
| `MODELO_CLAUDE_CODE` | `"sonnet"` (rápido) u `"opus"` (más detallado, más lento) |
| `ABRIR_GOOGLE` | `False` para no abrir Google |
| `GUARDAR_HISTORIAL` | `False` para no guardar `historial.md` |

## Problemas comunes

- **La caja queda desplazada respecto a lo que seleccioné**: avísame y te digo qué cambiar. El script ya tiene en cuenta el escalado de pantalla (125 %, 150 %).
- **El atajo no hace nada en algún programa**: algunos programas que corren como administrador bloquean el atajo. Ejecuta `iniciar.bat` con clic derecho → *Ejecutar como administrador*.
- **No abre Brave**: el script lo busca en las rutas normales de instalación. Si no lo encuentra, usa el navegador predeterminado.
