"""Turns the Habit prototype (single HTML, localStorage + sample data) into the
connected app (Supabase via cloud.js):

    python3 tools/build_from_prototype.py tools/prototype.html index.html

Design changes go into the prototype first, then this rebuilds index.html."""
import sys, re
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()

def rep(a, b, n=1):
    global s
    c = s.count(a)
    assert c == n, (c, a[:90])
    s = s.replace(a, b)

def cut(start, end):
    """remove from start marker (inclusive) to end marker (exclusive)"""
    global s
    i = s.index(start); j = s.index(end, i)
    s = s[:i] + s[j:]

# ---------- document shell + PWA ----------
rep('<title>Habit</title>', '''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0D0F12">
<meta name="description" content="Tus hábitos del día, con tu amigo.">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Habit">
<title>Habit</title>''')
i = s.index('</style>') + len('</style>')
s = s[:i] + '\n</head>\n<body>' + s[i:]
s = s.rstrip() + '\n</body>\n</html>\n'

# ---------- auth + splash screens (markup + css) ----------
rep('<div class="app">', '''<div class="splash" id="splash" aria-hidden="true"><div class="splash-mark">Habit</div></div>
<div class="auth" id="auth" hidden></div>
<div class="app">''')
rep('</style>', '''
/* ---------- splash + login ---------- */
.splash{position:fixed;inset:0;z-index:80;display:grid;place-items:center;background:var(--bg);transition:opacity .35s var(--ease)}
.splash.out{opacity:0;pointer-events:none}
.splash-mark{font-family:var(--display);font-stretch:125%;font-weight:900;font-size:34px;letter-spacing:-.01em;color:var(--fg);animation:viewin .5s var(--ease)}
.auth{position:fixed;inset:0;z-index:70;overflow:auto;background:var(--bg);display:flex;flex-direction:column}
.auth-art{position:relative;height:min(42vh,320px);flex:none;overflow:hidden}
.auth-art svg{position:absolute;inset:0;width:100%;height:100%}
.auth-art::after{content:"";position:absolute;inset:auto 0 0 0;height:40%;background:linear-gradient(transparent,var(--bg))}
.auth-in{width:min(440px,100%);margin:0 auto;padding:0 20px calc(28px + env(safe-area-inset-bottom,0px));display:flex;flex-direction:column;gap:14px;flex:1;animation:viewin .35s var(--ease)}
.auth-brand{font-family:var(--display);font-stretch:125%;font-weight:900;font-size:15px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent)}
.auth h1{margin:0;font-family:var(--display);font-stretch:118%;font-weight:900;font-size:34px;line-height:1.02;letter-spacing:-.01em}
.auth p{margin:0;color:var(--muted);font-size:15px;line-height:1.45}
.auth p b{color:var(--fg)}
.auth input{width:100%;font:inherit;font-size:17px;color:var(--fg);background:var(--surface);border:1.5px solid var(--line);border-radius:16px;padding:16px;outline:none}
.auth input:focus{border-color:var(--accent)}
.auth input.code{font-family:var(--display);font-stretch:125%;font-weight:800;font-size:28px;letter-spacing:.24em;text-align:center;padding:14px 0 14px .24em}
.auth .field{gap:8px;margin-top:6px}
.auth-err{min-height:20px;color:#FF8A8A;font-size:14px;font-weight:600}
.auth-links{display:flex;justify-content:space-between;gap:12px}
.link{color:var(--muted);font-weight:700;font-size:14px;padding:10px 0;text-decoration:underline;text-underline-offset:3px}
.link:disabled{opacity:.45;text-decoration:none}
.auth-foot{margin-top:auto;padding-top:18px;color:var(--faint);font-size:13px;text-align:center}
.btn.loading{opacity:.6;pointer-events:none}
/* ---------- invite (no friend yet) ---------- */
.invite{display:flex;flex-direction:column;align-items:center;text-align:center;gap:14px;padding:26px 18px 22px;border-radius:26px;background:var(--surface);border:1px solid var(--line)}
.invite svg.pair{width:150px;height:84px}
.invite h3{margin:0;font-family:var(--display);font-stretch:118%;font-weight:900;font-size:24px;line-height:1.1}
.invite p{margin:0;color:var(--muted);font-size:15px;line-height:1.45;max-width:32ch}
.invite .btn{margin-top:6px}
.acct{color:var(--muted);font-size:14px;word-break:break-all}
/* ---------- friends: one pair each, pick who to look at ---------- */
.fpick{margin-bottom:-6px}
.fpick .fchip{display:inline-flex;align-items:center;gap:7px;padding:6px 14px 6px 6px}
.fpick .fchip .avatar{width:26px;height:26px;border-radius:9px;font-size:12px}
.fpick .fchip.on .avatar.f{background:var(--ink);color:var(--fg);box-shadow:none}
.fpick .fchip.add{padding:6px 14px;color:var(--muted)}
.fpick .fchip.add svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:2.4;stroke-linecap:round}
.unfriend{display:block;margin:4px auto 0}
</style>''')

# ---------- module script + async boot ----------
rep('<script>\n(function(){', "<script type=\"module\">\nimport * as cloud from './cloud.js';\n(async function(){")

# ---------- remove sample data ----------
cut('function rng(seed){', '/* ---------- state ---------- */')
cut('function load(){', 'function save(){')
rep("function save(){ try { localStorage.setItem(KEY, JSON.stringify(state)); return true; } catch(e){ return false; } }",
    "function save(){ return sync ? sync.save(state) : true; }")
rep('''let state = load() || seed();
const friend = seedFriend();''', '''const emptyState = () => ({habits:[], log:{}, frozen:{}, profile:{name:'', accent:ACCENTS[0], accentSet:true}});
let state = emptyState(), friends = [], friend = null, sync = null, me = null;''')
rep("const newId = () => 'h' + Date.now().toString(36) + Math.random().toString(36).slice(2,6);",
    "const newId = () => crypto.randomUUID();")

# ---------- photos: stored as private paths, shown through signed links ----------
rep("const photosOf = e => (e && e.photos) || [];", '''const rawPhotos = e => (e && e.photos) || [];
const photosOf = e => rawPhotos(e).map(p => cloud.photoURL(p, photosReady));
let photoTimer = null;
function photosReady(){
  clearTimeout(photoTimer);
  photoTimer = setTimeout(() => {
    render();
    if (!ui.sheet) return;
    if (ui.sheet.mode === 'note') document.querySelectorAll('.photo-row .ph img').forEach((img,i) => { img.src = cloud.photoURL(ui.photoDraft[i], photosReady); });
    else renderSheet();
  }, 20);
}''')
rep("ui.noteDraft = e.note || ''; ui.photoDraft = [...photosOf(e)]; }", "ui.noteDraft = e.note || ''; ui.photoDraft = [...rawPhotos(e)]; }")
rep("JSON.stringify(photos) === JSON.stringify(photosOf(prev))) return null;", "JSON.stringify(photos) === JSON.stringify(rawPhotos(prev))) return null;")
rep('${ui.photoDraft.map((src,i) => `<div class="ph"><img src="${src}"', '${ui.photoDraft.map((src,i) => `<div class="ph"><img src="${cloud.photoURL(src, photosReady)}"')

# ---------- friend may not exist yet ----------
rep("  const a = dayStatus(state,k), b = dayStatus(friend,k);", "  if (!friend) return null;\n  const a = dayStatus(state,k), b = dayStatus(friend,k);")
rep("function friendNews(since){\n  const t = todayKey(), items = [];", "function friendNews(since){\n  if (!friend) return 0;\n  const t = todayKey(), items = [];")
rep("  const news = ui.tab === 'friend' ? 0 : friendNews(state.friendSeenAt || 0);",
    "  const news = ui.tab === 'friend' ? 0 : friends.reduce((n, f) => n + withFriend(f, () => friendNews(state.friendSeenAt || 0)), 0);")
rep("  $('view-friend').innerHTML = html;\n}", "  $('view-friend').innerHTML = friendPicker() + html + unfriendHTML(fname);\n}")
rep("<span>Tu amigo verá tus notas y fotos.", "<span>${friends.length > 1 ? 'Tus amigos verán' : 'Tu amigo verá'} tus notas y fotos.")
rep("  if (ui.tab === 'friend') { $('eyebrow').textContent = 'Vista previa'; $('title').textContent = 'Tu amigo'; return; }",
    "  if (ui.tab === 'friend') { $('eyebrow').textContent = friend ? 'Tu amigo' : 'Juntos'; $('title').textContent = friend ? friendName() : 'Tu amigo'; return; }")
rep('''function renderFriend(){
  const t = todayKey(), since = ui.friendPrevSeen || 0;''', '''const friendName = () => (friend && friend.profile.name) || 'Tu amigo';
const PAIR_SVG = `<svg class="pair" viewBox="0 0 150 84" aria-hidden="true"><path d="M44 58 C64 30 86 30 106 58" fill="none" stroke="var(--faint)" stroke-width="2.5" stroke-dasharray="1 7" stroke-linecap="round"/><circle cx="34" cy="50" r="22" fill="var(--accent)"/><circle cx="116" cy="50" r="22" fill="var(--surface-2)" stroke="var(--faint)" stroke-width="2" stroke-dasharray="4 5"/><path d="M116 42v16M108 50h16" stroke="var(--muted)" stroke-width="2.6" stroke-linecap="round"/><g fill="var(--ink)"><circle cx="34" cy="44" r="6"/><path d="M23 62c2-6 6-9 11-9s9 3 11 9"/></g></svg>`;
function renderInvite(){
  $('view-friend').innerHTML = `<div class="invite">
    ${PAIR_SVG}
    <h3>Hagan hábitos juntos</h3>
    <p>Invita a tu amigo. Verán el día del otro, sus notas y fotos, y tendrán una racha que solo sube si los dos cumplen.</p>
    <button class="btn wide" data-act="invite">Invitar a mi amigo</button>
    <div class="hint">Cuando entre con tu enlace, aparecerá aquí. Puedes invitar a más de un amigo: cada uno ve tu día, pero no el de los otros.</div>
  </div>`;
}
/* Each friendship is its own pair. Chips pick whose day is on screen; "Invitar" adds another pair. */
function withFriend(f, fn){ const prev = friend; friend = f; try { return fn(); } finally { friend = prev; } }
function friendPicker(){
  return `<div class="filters fpick" role="tablist" aria-label="Tus amigos">${friends.map(f => `<button class="fchip${f === friend ? ' on' : ''}" data-act="pick-friend" data-id="${esc(f.id)}" role="tab" aria-selected="${f === friend}"><span class="avatar f">${esc(initial(f.profile.name) || 'A')}</span>${esc(f.profile.name || 'Tu amigo')}</button>`).join('')}<button class="fchip add" data-act="invite">${PLUS_SVG}Invitar</button></div>`;
}
const unfriendHTML = name => `<button class="link unfriend" data-act="unfriend" data-id="${esc(friend.id)}">${ui.confirmUnfriend === friend.id ? `¿Seguro? Toca otra vez para dejar de ser amigos con ${esc(name)}` : `Dejar de ser amigos con ${esc(name)}`}</button>`;
function renderFriend(){
  if (!friend) return renderInvite();
  const fname = friendName();
  const t = todayKey(), since = ui.friendPrevSeen || 0;''')
rep("`Ya cumpliste. Falta tu amigo para sumar el día ${shared + 1}.`", "`Ya cumpliste. Falta ${fname} para sumar el día ${shared + 1}.`")
rep("`Tu amigo ya cumplió. Te falta a ti para sumar el día ${shared + 1}.`", "`${fname} ya cumplió. Te falta a ti para sumar el día ${shared + 1}.`")
rep("${row({l:'A', f:true}, 'Tu amigo', p, frDone)}", "${row({l:initial(fname) || 'A', f:true}, fname, p, frDone)}")
rep("· tu amigo ${s.cur}</div>", "· ${esc(fname)} ${s.cur}</div>")
i0 = s.index("  const frDone = withState(friend, () => isFull(t) || isRest(t)), frP"); j0 = s.index("\n", s.index("  const fr = frDone ?", i0)) + 1
s = s[:i0] + '''  let fr = '';
  if (friends.length === 1) withFriend(friends[0], () => {
    const frDone = withState(friend, () => isFull(t) || isRest(t)), frP = withState(friend, () => Math.round(dayPct(t)*100));
    fr = frDone ? `${friendName()} también cumplió. Racha juntos: ${sharedStreak()}.` : `${friendName()} va al ${frP}\u00a0%. Falta para sumar juntos.`;
  });
  else if (friends.length > 1) {
    const done = friends.filter(f => withState(f, () => isFull(t) || isRest(t))).length;
    fr = done ? `${done} de ${friends.length} amigos también cumplieron hoy.` : 'Tus amigos todavía no completan su día.';
  }
''' + s[j0:]
rep('      <p class="cel-fr">${esc(fr)}</p>', "      ${fr ? `<p class=\"cel-fr\">${esc(fr)}</p>` : ''}")
rep("  freezePast(); withState(friend, freezePast); save(); render();\n  toast('Nuevo día. El de ayer quedó guardado.');",
    "  freezePast(); friends.forEach(f => withState(f, freezePast)); save(); render();\n  toast('Nuevo día. El de ayer quedó guardado.');")

rep("    $('eyebrow').textContent = 'Habit · para ti y tu amigo';", "    $('eyebrow').textContent = friends.length === 1 ? `Habit · con ${friendName()}` : friends.length ? 'Habit · con tus amigos' : 'Habit · para ti y tu amigo';")

# ---------- profile: account instead of sample reset ----------
rep('''      ${state.sample ? `<div class="field"><span class="lbl">Datos de ejemplo</span>
        <button class="btn danger wide" data-act="reset">${ui.confirmReset ? '¿Seguro? Toca otra vez' : 'Borrar ejemplos y empezar de cero'}</button></div>` : ''}''',
'''      <div class="field"><span class="lbl">Cuenta</span>
        <div class="acct">${esc((me && me.email) || '')}${friends.length ? ` · conectado con ${esc(friends.map(f => f.profile.name || 'Tu amigo').join(', '))}` : ''}</div>
        <button class="btn ghost wide" data-act="signout">Cerrar sesión</button></div>''')
rep('''    case 'reset':''', '''    case 'signout':
      b.classList.add('loading');
      sync.flush().catch(() => {}).then(() => cloud.signOut(me.id)).finally(() => location.reload());
      break;
    case 'invite': shareInvite(b); break;
    case 'pick-friend':
      friend = friends.find(f => f.id === b.dataset.id) || friend; ui.friendId = friend && friend.id; ui.confirmUnfriend = null;
      render(); window.scrollTo({top:0}); break;
    case 'unfriend': {
      const id = b.dataset.id, f = friends.find(x => x.id === id); if (!f) break;
      if (ui.confirmUnfriend !== id) { ui.confirmUnfriend = id; render(); break; }
      b.classList.add('loading');
      cloud.removeFriend(id).then(refreshFriends).then(() => {
        ui.confirmUnfriend = null; render(); window.scrollTo({top:0});
        toast(`Ya no eres amigo de ${f.profile.name || 'esa persona'}`);
      }).catch(() => { b.classList.remove('loading'); toast('No se pudo. Revisa tu internet.'); });
      break;
    }
    case 'reset':''')

# ---------- boot ----------
rep('''freezePast(); withState(friend, freezePast); save();
render();
})();''', r'''/* ---------- cuenta, amigo y arranque ---------- */
const INVITE_KEY = 'ritmo-invite';
/* The login reuses the day's mountain: same drawing, own gradient ids, no climber yet. */
const AUTH_ART = `<svg class="climb" viewBox="0 0 360 150" preserveAspectRatio="xMidYMax slice" aria-hidden="true">${$('climb').innerHTML
  .replace(/<path class="trail-done"[^>]*>(<\/path>)?/, '').replace(/<g class="climber"[\s\S]*<\/g>\s*<\/g>/, '')
  .replace(/id="([^"]+)"/g, 'id="au-$1"').replace(/url\(#/g, 'url(#au-')}</svg>`;
let offlineShown = false;
function setSyncStatus(st){
  if (st === 'offline' && !offlineShown) { offlineShown = true; toast('Sin conexión. Se guardará cuando vuelva.'); }
  if (st === 'saved') offlineShown = false;
}
function hideSplash(){ const sp = $('splash'); sp.classList.add('out'); clearTimeout(ui.splashT); ui.splashT = setTimeout(() => { sp.hidden = true; }, 400); }
/* Covers the app while the first load runs, so the empty "Hoy" skeleton never flashes. */
function showSplash(){ const sp = $('splash'); clearTimeout(ui.splashT); sp.hidden = false; sp.classList.remove('out'); }
function authScreen(html){ const a = $('auth'); a.hidden = false; a.innerHTML = `<div class="auth-art">${AUTH_ART}</div><div class="auth-in">${html}</div>`; hideSplash(); return a; }
const AUTH_ERRORS = [[/rate|seconds|too many/i, 'Espera un momento antes de pedir otro código.'], [/expired|invalid|token/i, 'Ese código no es correcto o ya venció.'], [/email/i, 'Revisa que el correo esté bien escrito.']];
const authMsg = err => (AUTH_ERRORS.find(([re]) => re.test((err && err.message) || '')) || [0, 'No se pudo conectar. Revisa tu internet.'])[1];
/* Login sin contraseña: correo → código numérico. Supabase puede enviar 6 u 8 dígitos
   (según la plantilla y la configuración), así que se aceptan de 6 a 10. Resuelve con el usuario. */
function authFlow(){
  return new Promise(resolve => {
    let email = '';
    try { email = localStorage.getItem('ritmo-email') || ''; } catch(e) {}
    const invited = (() => { try { return !!localStorage.getItem(INVITE_KEY); } catch(e) { return false; } })();
    const stepEmail = () => {
      const a = authScreen(`<div class="auth-brand">Habit</div>
        <h1>${invited ? 'Te invitaron a Habit' : 'Tus hábitos, con tus amigos.'}</h1>
        <p>${invited ? 'Entra con tu correo y quedarán conectados.' : 'Marca tu día, sube la montaña y mantengan la racha juntos.'}</p>
        <div class="field"><label class="lbl" for="au-email">Tu correo</label>
          <input id="au-email" type="email" inputmode="email" autocomplete="email" autocapitalize="off" spellcheck="false" placeholder="tu@correo.com" value="${esc(email)}" enterkeyhint="send"></div>
        <div class="auth-err" id="au-err" role="alert"></div>
        <button class="btn wide" id="au-send">Enviarme un código</button>
        <div class="auth-foot">Sin contraseñas. Te llega un código por correo.</div>`);
      const inp = a.querySelector('#au-email'), btn = a.querySelector('#au-send'), err = a.querySelector('#au-err');
      const go = async () => {
        email = inp.value.trim().toLowerCase();
        if (!/^\S+@\S+\.\S+$/.test(email)) { err.textContent = 'Escribe un correo válido.'; inp.focus(); return; }
        btn.classList.add('loading'); err.textContent = '';
        try { await cloud.sendCode(email); try { localStorage.setItem('ritmo-email', email); } catch(e) {} stepCode(); }
        catch(e2) { err.textContent = authMsg(e2); btn.classList.remove('loading'); }
      };
      btn.onclick = go; inp.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); go(); } };
      setTimeout(() => inp.focus(), 350);
    };
    const stepCode = () => {
      const a = authScreen(`<div class="auth-brand">Habit</div>
        <h1>Revisa tu correo</h1>
        <p>Te enviamos un código a <b>${esc(email)}</b>. Si no aparece, mira en spam.</p>
        <div class="field"><label class="lbl" for="au-code">Código</label>
          <input id="au-code" class="code" type="text" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]*" maxlength="10" placeholder="········"></div>
        <div class="auth-err" id="au-err" role="alert"></div>
        <button class="btn wide" id="au-verify">Entrar</button>
        <div class="auth-links"><button class="link" id="au-back">Usar otro correo</button><button class="link" id="au-resend" disabled>Reenviar en 30 s</button></div>`);
      const inp = a.querySelector('#au-code'), btn = a.querySelector('#au-verify'), err = a.querySelector('#au-err'), rs = a.querySelector('#au-resend');
      let left = 30; const tick = setInterval(() => { left--; rs.textContent = left > 0 ? `Reenviar en ${left} s` : 'Reenviar código'; rs.disabled = left > 0; if (left <= 0) clearInterval(tick); }, 1000);
      const go = async () => {
        const code = inp.value.replace(/\D/g, '');
        clearTimeout(autoGo);
        if (code.length < 6) { err.textContent = 'Escribe el código completo que te llegó.'; inp.focus(); return; }
        if (btn.classList.contains('loading')) return;
        btn.classList.add('loading'); err.textContent = '';
        try { const u = await cloud.verifyCode(email, code); clearInterval(tick); buzz(12); resolve(u); }
        catch(e2) { err.textContent = authMsg(e2); btn.classList.remove('loading'); inp.select(); }
      };
      /* No sabemos si el código trae 6 u 8 dígitos: se envía solo al dejar de escribir (o al pegarlo). */
      let autoGo = null;
      inp.oninput = () => { inp.value = inp.value.replace(/\D/g, '').slice(0,10); clearTimeout(autoGo); if (inp.value.length >= 6) autoGo = setTimeout(go, inp.value.length >= 8 ? 300 : 2000); };
      btn.onclick = go;
      a.querySelector('#au-back').onclick = () => { clearInterval(tick); stepEmail(); };
      rs.onclick = async () => { rs.disabled = true; try { await cloud.sendCode(email); toast('Código reenviado'); left = 30; } catch(e2) { err.textContent = authMsg(e2); rs.disabled = false; } };
      setTimeout(() => inp.focus(), 350);
    };
    stepEmail();
  });
}
async function refreshFriends(){
  try {
    const list = await cloud.loadFriends(me.id);
    list.forEach(f => { normalize(f); withState(f, freezePast); });
    const changed = JSON.stringify(list) !== JSON.stringify(friends);
    friends = list;
    friend = friends.find(f => f.id === ui.friendId) || friends[0] || null;
    ui.friendId = friend && friend.id;
    return changed;
  } catch(e) { console.warn('[ritmo] friends', e); return false; }
}
async function acceptPendingInvite(){
  let code = null; try { code = localStorage.getItem(INVITE_KEY); } catch(e) {}
  if (!code) return;
  try {
    ui.friendId = await cloud.acceptInvite(code);
    await refreshFriends();
    if (friend) { if (active().length) ui.tab = 'friend'; setTimeout(() => toast(`Ya estás conectado con ${friendName()}`), 400); }
  } catch(e) {
    const m = (e && e.message) || '';
    if (/too_many_friends/.test(m)) toast('Llegaste al máximo de amigos.');
    else if (/invite_used|invite_not_found/.test(m)) toast('Ese enlace ya no sirve. Pídele uno nuevo.');
    else if (!/own_invite/.test(m)) { toast('No se pudo usar la invitación. Inténtalo de nuevo.'); return; }
  }
  try { localStorage.removeItem(INVITE_KEY); } catch(e) {}
}
async function shareInvite(btn){
  btn.classList.add('loading');
  try {
    const code = await cloud.createInvite();
    const url = `${location.origin}${location.pathname}?i=${code}`;
    const text = `${state.profile.name || 'Tu amigo'} te invita a Habit para hacer hábitos juntos.`;
    if (navigator.share) { try { await navigator.share({title:'Habit', text, url}); } catch(e) { if (e.name !== 'AbortError') throw e; } }
    else { await navigator.clipboard.writeText(`${text} ${url}`); toast('Enlace copiado. Pégalo en WhatsApp.'); }
  } catch(e) { toast('No se pudo crear la invitación. Revisa tu internet.'); }
  btn.classList.remove('loading');
}
function setupScreen(){
  authScreen(`<div class="auth-brand">Habit</div><h1>Falta conectar la base de datos</h1>
    <p>Copia la URL y la clave pública de tu proyecto de Supabase en <b>config.js</b>. Los pasos están en el README.</p>`);
}
async function boot(){
  const inv = new URLSearchParams(location.search).get('i');
  if (inv) { try { localStorage.setItem(INVITE_KEY, inv); } catch(e) {} history.replaceState(null, '', location.pathname); }
  if (!cloud.configured) return setupScreen();
  me = await cloud.currentUser().catch(() => null);
  if (!me) { me = await authFlow(); showSplash(); $('auth').hidden = true; }
  sync = cloud.createSync(me.id, {
    getState: () => state,
    photoUploaded: (dataUrl, path) => cloud.rememberPhoto(dataUrl, path),
    status: setSyncStatus,
    closedDay: () => {}
  });
  const cached = sync.cached();
  if (cached) { state = normalize(cached); freezePast(); render(); hideSplash(); }
  try { state = normalize(await sync.load()); }
  catch(e) {
    console.warn('[ritmo] load', e);
    if (!cached) { authScreen('<div class="auth-brand">Habit</div><h1>No pudimos cargar tu día</h1><p>Revisa tu conexión y vuelve a abrir la app.</p>'); return; }
  }
  await refreshFriends();
  await acceptPendingInvite();
  freezePast(); save(); render(); hideSplash();
  const poll = async () => { if (!document.hidden && await refreshFriends() && !ui.sheet) render(); };
  setInterval(poll, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); else sync.flush(); });
  window.addEventListener('online', () => sync.flush());
  window.addEventListener('pagehide', () => sync.flush());
}
await boot();
})();''')

open(dst, 'w', encoding='utf-8').write(s)
print('ok', len(s))
