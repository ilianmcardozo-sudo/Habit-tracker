# Habit

Tus hábitos del día, con tus amigos. Marca lo que hiciste, sube la montaña hasta el 100 % y mantengan la racha juntos.

- Entras con tu correo y un código que te llega por correo (6 u 8 dígitos). No hay contraseñas.
- El día cierra a las 4:00 (hora del teléfono). Después ya no se puede cambiar, y eso lo valida la base de datos.
- Las amistades son siempre de a dos. Puedes tener varios amigos, pero cada pareja es independiente: cada amigo ve tu día completo (con notas y fotos), no el de tus otros amigos. Nadie más puede verlo.
- Cada pareja tiene su propia racha juntos, que solo sube si los dos cumplen.
- Se instala en el teléfono como una app: Compartir → "Añadir a pantalla de inicio".

Es una página estática (`index.html` + `cloud.js`), sin build. Supabase guarda las cuentas, los datos y las fotos.

## Puesta en marcha (una sola vez)

### 1. Supabase

1. Crea una cuenta en [supabase.com](https://supabase.com) y luego **New project**. Elige la región más cercana y guarda la contraseña de la base de datos en un lugar seguro.
2. Ve a **SQL Editor → New query**, pega todo `supabase/schema.sql` y pulsa **Run**. Esto crea las tablas, los permisos, el candado de las 4:00 y el almacenamiento privado de fotos.
3. Ve a **Authentication → Emails → Templates → Magic Link** y cambia el contenido para que envíe el código:
   - Asunto: `Tu código de Habit: {{ .Token }}`
   - Cuerpo:
     ```html
     <h2>Tu código para entrar a Habit</h2>
     <p style="font-size:32px;font-weight:700;letter-spacing:6px">{{ .Token }}</p>
     <p>Vence en 1 hora. Si no lo pediste, ignora este correo.</p>
     ```
4. Ve a **Authentication → Sign In / Providers → Email** y revisa que **Email OTP Length** esté en **6**.
5. Ve a **Project Settings → API** y copia la **Project URL** y la clave **anon public** en `config.js`.

   > La clave `anon` es pública por diseño; los datos los protegen las reglas de `schema.sql`. **Nunca** pongas la `service_role` en este repositorio.

### 2. Vercel

1. Entra a [vercel.com](https://vercel.com) con tu cuenta de GitHub, elige **Add New → Project** e importa este repositorio.
2. En Framework Preset elige **Other**. No hace falta configurar nada más y puedes pulsar **Deploy**.
3. Copia la dirección que te da Vercel (por ejemplo `https://ritmo-tuusuario.vercel.app`). En Supabase ve a **Authentication → URL Configuration** y ponla en **Site URL**.

### 3. Usarla

1. Abre la dirección en tu teléfono, entra con tu correo y elige tus hábitos.
2. En **Amigo**, toca **Invitar a mi amigo** y mándale el enlace.
3. Cuando entre con ese enlace, quedan conectados. Cada enlace sirve para una sola persona.
4. Para sumar otro amigo, toca **+ Invitar** arriba en **Amigo** y manda el nuevo enlace. Con las etiquetas de arriba eliges de quién ver el día. Abajo del todo está **Dejar de ser amigos**.
5. Para instalarla:
   - iPhone: Safari → Compartir → **Añadir a pantalla de inicio**.
   - Android: Chrome → ⋮ → **Instalar app**.

> El plan gratis de Supabase envía pocos correos por hora. Para unos pocos amigos sobra. Si algún día se queda corto, conecta un SMTP propio (por ejemplo Resend) en **Authentication → Emails → SMTP Settings**.

## Estructura

| Archivo | Qué es |
| --- | --- |
| `index.html` | La app completa: diseño, pantallas y lógica de hábitos. |
| `cloud.js` | Conexión con Supabase: login, guardado en segundo plano, amigos, invitaciones y fotos privadas. |
| `config.js` | URL y clave pública de tu proyecto de Supabase. |
| `supabase/schema.sql` | Tablas, permisos (RLS), candado de las 4:00 y almacenamiento de fotos. |
| `manifest.webmanifest`, `icons/` | Lo necesario para instalarla como app. |
| `tools/prototype.html` | El prototipo de diseño (datos de ejemplo, sin conexión). Los cambios de diseño se hacen aquí. |
| `tools/build_from_prototype.py` | Convierte el prototipo en `index.html` conectado: `python3 tools/build_from_prototype.py tools/prototype.html index.html` |

## Cómo se guardan los datos

- La app trabaja sobre su estado en memoria. Cada cambio se guarda al instante en el teléfono y se sube unos milisegundos después, enviando solo lo que cambió.
- Si no hay conexión, lo pendiente queda en el teléfono y se sube cuando vuelve la conexión.
- Lo que manda es el servidor. Si intentas cambiar un día que ya cerró a las 4:00, la base de datos lo rechaza.
- Las fotos se suben a un almacenamiento privado (`photos/<tu-id>/<día>/…`) y se muestran con enlaces temporales. Solo tú y tus amigos pueden verlas.
