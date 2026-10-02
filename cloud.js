/* Habit · conexión con Supabase.
   La app trabaja siempre sobre su estado en memoria (como el prototipo) y este
   módulo lo carga, lo guarda en segundo plano y trae los datos del amigo.
   Las reglas importantes (candado de las 4:00, quién ve qué) las aplica la
   base de datos, no el teléfono. */
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './config.js';

export const configured = !!(SUPABASE_URL && SUPABASE_ANON_KEY && !SUPABASE_URL.includes('TU-PROYECTO'));
export const sb = configured ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false }
}) : null;

const TZ = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (e) { return 'UTC'; } })();
const PENDING_KEY = uid => `ritmo-pending-${uid}`;
const CACHE_KEY = uid => `ritmo-cache-${uid}`;
const clone = o => JSON.parse(JSON.stringify(o));

/* ---------- sesión ---------- */
export async function currentUser() {
  const { data } = await sb.auth.getSession();
  return data.session ? data.session.user : null;
}
export async function sendCode(email) {
  const { error } = await sb.auth.signInWithOtp({ email, options: { shouldCreateUser: true } });
  if (error) throw error;
}
export async function verifyCode(email, token) {
  const { data, error } = await sb.auth.verifyOtp({ email, token, type: 'email' });
  if (error) throw error;
  return data.user;
}
export async function signOut(uid) {
  try { localStorage.removeItem(CACHE_KEY(uid)); localStorage.removeItem(PENDING_KEY(uid)); } catch (e) {}
  await sb.auth.signOut();
}

/* ---------- filas ⇄ estado ---------- */
const PROFILE_PREFS = ['accent', 'accentSet'];
const TOP_PREFS = ['friendSeenAt', 'fullAt', 'celebratedOn'];

function rowsToState(profile, habits, entries, frozen) {
  const prefs = (profile && profile.prefs) || {};
  const s = {
    habits: habits.sort((a, b) => a.position - b.position).map(r => ({ ...r.data, id: r.id })),
    log: {}, frozen: {},
    profile: { name: (profile && profile.name) || '' }
  };
  PROFILE_PREFS.forEach(k => { if (prefs[k] != null) s.profile[k] = prefs[k]; });
  TOP_PREFS.forEach(k => { if (prefs[k] != null) s[k] = prefs[k]; });
  entries.forEach(r => {
    (s.log[r.day] || (s.log[r.day] = {}))[r.habit_id] = { ...r.data, at: r.data.at || Date.parse(r.updated_at) };
  });
  frozen.forEach(r => { s.frozen[r.day] = r.data; });
  return s;
}
function profileRow(uid, s) {
  const prefs = {};
  PROFILE_PREFS.forEach(k => { if (s.profile[k] != null) prefs[k] = s.profile[k]; });
  TOP_PREFS.forEach(k => { if (s[k] != null) prefs[k] = s[k]; });
  return { id: uid, name: (s.profile.name || '').slice(0, 30), tz: TZ, prefs };
}
const habitRow = (uid, h, i) => { const { id, ...data } = h; return { id, user_id: uid, data, position: i }; };

async function fetchAll(table, col, uid, extra) {
  let q = sb.from(table).select('*').eq(col, uid);
  if (extra) q = extra(q);
  const { data, error } = await q;
  if (error) throw error;
  return data;
}
async function loadUser(uid, sinceDay) {
  const [p, h, e, f] = await Promise.all([
    sb.from('profiles').select('*').eq('id', uid).maybeSingle(),
    fetchAll('habits', 'user_id', uid),
    fetchAll('entries', 'user_id', uid, sinceDay ? q => q.gte('day', sinceDay) : null),
    fetchAll('frozen_days', 'user_id', uid, sinceDay ? q => q.gte('day', sinceDay) : null)
  ]);
  if (p.error) throw p.error;
  return { profile: p.data, state: rowsToState(p.data, h, e, f) };
}

/* ---------- sincronización ----------
   Guardamos una copia de lo último que el servidor confirmó. En cada cambio
   comparamos contra ella y mandamos solo lo distinto. Si no hay conexión, lo
   pendiente queda en el teléfono y se reintenta. */
export function createSync(uid, hooks) {
  let synced = null;        // último estado confirmado por el servidor
  let timer = null, running = false, again = false;

  const snapshot = s => ({
    profile: JSON.stringify(profileRow(uid, s)),
    habits: Object.fromEntries(s.habits.map((h, i) => [h.id, JSON.stringify(habitRow(uid, h, i))])),
    entries: Object.fromEntries(Object.entries(s.log).flatMap(([day, d]) => Object.entries(d).map(([hid, e]) => [`${day}|${hid}`, JSON.stringify(e)]))),
    frozen: Object.fromEntries(Object.entries(s.frozen || {}).map(([d, v]) => [d, JSON.stringify(v)]))
  });

  function cache(s) {
    try { localStorage.setItem(CACHE_KEY(uid), JSON.stringify(s)); } catch (e) {}
  }

  async function uploadPhotos(day, hid, e) {
    const out = [];
    for (const p of e.photos || []) {
      if (!p.startsWith('data:')) { out.push(p); continue; }
      const blob = await (await fetch(p)).blob();
      const path = `${uid}/${day}/${hid}-${crypto.randomUUID().slice(0, 8)}.jpg`;
      const { error } = await sb.storage.from('photos').upload(path, blob, { contentType: blob.type || 'image/jpeg', upsert: false });
      if (error) throw error;
      hooks.photoUploaded(p, path);
      out.push(path);
    }
    return out;
  }

  async function push() {
    if (running) { again = true; return; }
    running = true;
    try {
      do {
        again = false;
        const s = hooks.getState();
        const now = snapshot(s);
        const ops = [];

        if (now.profile !== synced.profile) ops.push(async () => {
          const { error } = await sb.from('profiles').upsert(JSON.parse(now.profile));
          if (error) throw error;
          synced.profile = now.profile;
        });

        const habitUps = Object.keys(now.habits).filter(id => now.habits[id] !== synced.habits[id]);
        const habitDels = Object.keys(synced.habits).filter(id => !(id in now.habits));
        if (habitUps.length) ops.push(async () => {
          const { error } = await sb.from('habits').upsert(habitUps.map(id => JSON.parse(now.habits[id])));
          if (error) throw error;
          habitUps.forEach(id => { synced.habits[id] = now.habits[id]; });
        });
        if (habitDels.length) ops.push(async () => {
          const { error } = await sb.from('habits').delete().in('id', habitDels);
          if (error) throw error;
          habitDels.forEach(id => { delete synced.habits[id]; });
        });

        const entryUps = Object.keys(now.entries).filter(k => now.entries[k] !== synced.entries[k]);
        const entryDels = Object.keys(synced.entries).filter(k => !(k in now.entries));
        for (const key of entryUps) ops.push(async () => {
          const [day, hid] = key.split('|');
          const e = s.log[day] && s.log[day][hid]; if (!e) return;
          if ((e.photos || []).some(p => p.startsWith('data:'))) e.photos = await uploadPhotos(day, hid, e);
          const data = clone(e);
          const { error } = await sb.from('entries').upsert({ user_id: uid, day, habit_id: hid, data });
          if (error) return rejected(key, error, () => { synced.entries[key] = now.entries[key]; });
          synced.entries[key] = JSON.stringify(e);
        });
        for (const key of entryDels) ops.push(async () => {
          const [day, hid] = key.split('|');
          const { error } = await sb.from('entries').delete().match({ user_id: uid, day, habit_id: hid });
          if (error) return rejected(key, error, () => { delete synced.entries[key]; });
          delete synced.entries[key];
        });

        const frozenNew = Object.keys(now.frozen).filter(d => !(d in synced.frozen));
        if (frozenNew.length) ops.push(async () => {
          const { error } = await sb.from('frozen_days').upsert(frozenNew.map(day => ({ user_id: uid, day, data: JSON.parse(now.frozen[day]) })), { ignoreDuplicates: true });
          if (error && !isPolicy(error)) throw error;
          frozenNew.forEach(d => { synced.frozen[d] = now.frozen[d]; });
        });

        for (const op of ops) await op();
        savePending();
        hooks.status(ops.length ? 'saved' : 'idle');
      } while (again);
    } catch (err) {
      console.warn('[ritmo] sync', err);
      savePending();
      hooks.status('offline');
      clearTimeout(timer); timer = setTimeout(push, 15000);
    } finally { running = false; }
  }

  const isPolicy = err => err && (err.code === '42501' || /row-level security|policy/i.test(err.message || ''));
  /* El servidor rechazó un cambio en un día ya cerrado: el servidor manda. */
  function rejected(key, err, accept) {
    if (!isPolicy(err)) throw err;
    accept();
    hooks.closedDay(key);
  }

  /* Lo que no se alcanzó a subir sobrevive a recargar la página. */
  function savePending() {
    try {
      const s = hooks.getState(), now = snapshot(s);
      const dirty = Object.keys(now.entries).some(k => now.entries[k] !== synced.entries[k])
        || Object.keys(synced.entries).some(k => !(k in now.entries))
        || Object.keys(now.habits).some(k => now.habits[k] !== synced.habits[k])
        || Object.keys(synced.habits).some(k => !(k in now.habits))
        || now.profile !== synced.profile;
      if (dirty) localStorage.setItem(PENDING_KEY(uid), JSON.stringify(s));
      else localStorage.removeItem(PENDING_KEY(uid));
    } catch (e) {}
  }

  return {
    /* Carga del servidor; si quedó algo pendiente sin subir, lo reaplica encima. */
    async load() {
      const { profile, state } = await loadUser(uid);
      synced = snapshot(state);
      if (!profile) synced.profile = '';      // perfil nuevo: se crea en el primer push
      let s = state;
      try {
        const pend = JSON.parse(localStorage.getItem(PENDING_KEY(uid)) || 'null');
        if (pend) s = pend;
      } catch (e) {}
      cache(s);
      return s;
    },
    cached() { try { return JSON.parse(localStorage.getItem(CACHE_KEY(uid)) || 'null'); } catch (e) { return null; } },
    save(s) {
      cache(s);
      clearTimeout(timer);
      timer = setTimeout(push, 600);
      savePending();
      return true;
    },
    flush: () => { clearTimeout(timer); return push(); }
  };
}

/* ---------- amigos ----------
   Cada amistad es una pareja independiente: traemos el día de cada amigo,
   en el orden en que se conectaron. */
export async function loadFriends(uid) {
  const { data, error } = await sb.from('friendships').select('friend_id, created_at').eq('user_id', uid).order('created_at');
  if (error) throw error;
  const since = new Date(Date.now() - 120 * 864e5).toISOString().slice(0, 10);
  return Promise.all((data || []).map(async r => {
    const { profile, state } = await loadUser(r.friend_id, since);
    state.id = r.friend_id;
    state.profile.name = (profile && profile.name) || 'Tu amigo';
    return state;
  }));
}
export async function removeFriend(friendId) {
  const { error } = await sb.rpc('remove_friend', { p_friend: friendId });
  if (error) throw error;
}
export async function createInvite() {
  const code = Array.from(crypto.getRandomValues(new Uint8Array(9)), b => 'abcdefghjkmnpqrstuvwxyz23456789'[b % 31]).join('');
  const { error } = await sb.from('invites').insert({ code });
  if (error) throw error;
  return code;
}
export async function acceptInvite(code) {
  const { data, error } = await sb.rpc('accept_invite', { p_code: code });
  if (error) throw error;
  return data;
}

/* ---------- fotos privadas: enlaces firmados por 7 días ---------- */
const urls = new Map(), waiting = new Set();
let urlTimer = null;
export function photoURL(path, onReady) {
  if (!path || path.startsWith('data:') || path.startsWith('http')) return path;
  const u = urls.get(path);
  if (u) return u;
  waiting.add(path);
  clearTimeout(urlTimer);
  urlTimer = setTimeout(async () => {
    const batch = [...waiting]; waiting.clear();
    const { data } = await sb.storage.from('photos').createSignedUrls(batch, 7 * 86400);
    (data || []).forEach(r => { if (r.signedUrl) urls.set(r.path, r.signedUrl); });
    onReady();
  }, 30);
  return 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';
}
export function rememberPhoto(dataUrl, path) { urls.set(path, dataUrl); }
