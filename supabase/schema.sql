-- Ritmo · esquema de base de datos para Supabase
-- Pégalo completo en Supabase → SQL Editor → New query → Run.
-- Se puede ejecutar más de una vez sin romper nada.

-- ───────────── Tablas ─────────────

-- Un perfil por cuenta. tz = zona horaria del teléfono, para cerrar el día a las 4:00 locales.
create table if not exists public.profiles (
  id         uuid primary key references auth.users on delete cascade,
  name       text not null default '' check (char_length(name) <= 30),
  tz         text not null default 'UTC',
  prefs      jsonb not null default '{}'::jsonb,   -- acento, última visita a Amigo, etc.
  updated_at timestamptz not null default now()
);

-- Hábitos. "data" guarda nombre, ícono, frecuencia, importancia, etc.
create table if not exists public.habits (
  id         text primary key,
  user_id    uuid not null references auth.users on delete cascade default auth.uid(),
  data       jsonb not null,
  position   int  not null default 0,
  updated_at timestamptz not null default now()
);
create index if not exists habits_user on public.habits (user_id);

-- Lo que hiciste cada día con cada hábito: check, sueño, nota y fotos.
create table if not exists public.entries (
  user_id    uuid not null references auth.users on delete cascade default auth.uid(),
  day        date not null,
  habit_id   text not null,
  data       jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, day, habit_id)
);

-- Foto fija de cada día cerrado: qué hábitos contaban y cuánto valía cada uno.
create table if not exists public.frozen_days (
  user_id uuid not null references auth.users on delete cascade default auth.uid(),
  day     date not null,
  data    jsonb not null,
  primary key (user_id, day)
);

-- Amistad: siempre de a dos. Cada pareja son dos filas (una por persona).
-- Puedes tener varios amigos, pero cada amistad es independiente:
-- tus amigos ven tu día, no el de tus otros amigos.
create table if not exists public.friendships (
  user_id    uuid not null references auth.users on delete cascade,
  friend_id  uuid not null references auth.users on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, friend_id),
  check (user_id <> friend_id)
);
-- Si ya habías creado la versión de un solo amigo (clave = user_id), pásala a parejas.
do $$ begin
  if not exists (select 1 from information_schema.key_column_usage
                 where table_schema = 'public' and table_name = 'friendships'
                   and constraint_name = 'friendships_pkey' and column_name = 'friend_id') then
    alter table public.friendships drop constraint if exists friendships_pkey;
    alter table public.friendships add primary key (user_id, friend_id);
  end if;
end $$;

-- Invitaciones: el enlace que mandas por WhatsApp.
create table if not exists public.invites (
  code        text primary key check (char_length(code) between 8 and 40),
  inviter     uuid not null references auth.users on delete cascade default auth.uid(),
  created_at  timestamptz not null default now(),
  accepted_by uuid references auth.users on delete set null
);

-- ───────────── Funciones ─────────────

-- El "hoy" de una persona: su hora local menos 4 horas. Antes de las 4:00 sigue siendo ayer.
create or replace function public.ritmo_today(uid uuid)
returns date language sql stable security definer set search_path = public as $$
  select ((now() at time zone coalesce((select tz from profiles where id = uid), 'UTC')) - interval '4 hours')::date
$$;

-- ¿owner es mi amigo?
create or replace function public.is_friend(owner uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from friendships where user_id = auth.uid() and friend_id = owner)
$$;

-- Aceptar una invitación: conecta a las dos personas como pareja de amigos.
-- Cada enlace sirve una sola vez; para otro amigo se crea otro enlace.
create or replace function public.accept_invite(p_code text)
returns uuid language plpgsql security definer set search_path = public as $$
declare inv invites; me uuid := auth.uid();
begin
  if me is null then raise exception 'not_authenticated'; end if;
  select * into inv from invites where code = p_code for update;
  if not found then raise exception 'invite_not_found'; end if;
  if inv.inviter = me then raise exception 'own_invite'; end if;
  if exists (select 1 from friendships where user_id = me and friend_id = inv.inviter) then return inv.inviter; end if;
  if inv.accepted_by is not null then raise exception 'invite_used'; end if;
  if (select count(*) from friendships where user_id = me) >= 20
     or (select count(*) from friendships where user_id = inv.inviter) >= 20 then raise exception 'too_many_friends'; end if;
  insert into friendships (user_id, friend_id) values (me, inv.inviter), (inv.inviter, me);
  update invites set accepted_by = me where code = p_code;
  return inv.inviter;
end $$;

-- Dejar de ser amigos: borra la pareja en los dos sentidos. Los demás amigos no cambian.
create or replace function public.remove_friend(p_friend uuid)
returns void language sql security definer set search_path = public as $$
  delete from friendships
  where (user_id = auth.uid() and friend_id = p_friend)
     or (user_id = p_friend and friend_id = auth.uid())
$$;

-- Valida tz para que nadie pueda mover su "hoy" con una zona inventada.
create or replace function public.check_tz() returns trigger language plpgsql as $$
begin
  if not exists (select 1 from pg_timezone_names where name = new.tz) then new.tz := 'UTC'; end if;
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists profiles_tz on public.profiles;
create trigger profiles_tz before insert or update on public.profiles for each row execute function public.check_tz();

create or replace function public.touch() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end $$;
drop trigger if exists habits_touch on public.habits;
create trigger habits_touch before update on public.habits for each row execute function public.touch();
drop trigger if exists entries_touch on public.entries;
create trigger entries_touch before update on public.entries for each row execute function public.touch();

-- ───────────── Permisos (Row Level Security) ─────────────
alter table public.profiles    enable row level security;
alter table public.habits      enable row level security;
alter table public.entries     enable row level security;
alter table public.frozen_days enable row level security;
alter table public.friendships enable row level security;
alter table public.invites     enable row level security;

-- Leer: lo tuyo y lo de tus amigos (incluidas notas, como acordamos).
drop policy if exists "read own or friend" on public.profiles;
create policy "read own or friend" on public.profiles for select using (id = auth.uid() or public.is_friend(id));
drop policy if exists "read own or friend" on public.habits;
create policy "read own or friend" on public.habits for select using (user_id = auth.uid() or public.is_friend(user_id));
drop policy if exists "read own or friend" on public.entries;
create policy "read own or friend" on public.entries for select using (user_id = auth.uid() or public.is_friend(user_id));
drop policy if exists "read own or friend" on public.frozen_days;
create policy "read own or friend" on public.frozen_days for select using (user_id = auth.uid() or public.is_friend(user_id));
drop policy if exists "read own" on public.friendships;
create policy "read own" on public.friendships for select using (user_id = auth.uid());

-- Escribir: solo lo tuyo.
drop policy if exists "write own" on public.profiles;
create policy "write own" on public.profiles for insert with check (id = auth.uid());
drop policy if exists "update own" on public.profiles;
create policy "update own" on public.profiles for update using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists "write own" on public.habits;
create policy "write own" on public.habits for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- El candado de las 4:00: solo se puede tocar el día de hoy.
drop policy if exists "today only" on public.entries;
create policy "today only" on public.entries for all
  using (user_id = auth.uid() and day >= public.ritmo_today(auth.uid()))
  with check (user_id = auth.uid() and day >= public.ritmo_today(auth.uid()) and day <= public.ritmo_today(auth.uid()) + 1);

-- Los días cerrados se guardan una sola vez y no se cambian.
drop policy if exists "insert closed days" on public.frozen_days;
create policy "insert closed days" on public.frozen_days for insert
  with check (user_id = auth.uid() and day < public.ritmo_today(auth.uid()));

drop policy if exists "create own" on public.invites;
create policy "create own" on public.invites for insert with check (inviter = auth.uid() and accepted_by is null);
drop policy if exists "read own" on public.invites;
create policy "read own" on public.invites for select using (inviter = auth.uid());

-- ───────────── Fotos (Storage) ─────────────
-- Carpeta por persona: <user_id>/<día>/<archivo>.jpg. Privado: solo tú y tus amigos.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('photos', 'photos', false, 2097152, array['image/jpeg','image/png','image/webp'])
on conflict (id) do nothing;

drop policy if exists "photos read own or friend" on storage.objects;
create policy "photos read own or friend" on storage.objects for select
  using (bucket_id = 'photos' and ((storage.foldername(name))[1] = auth.uid()::text
         or public.is_friend(((storage.foldername(name))[1])::uuid)));
drop policy if exists "photos upload own today" on storage.objects;
create policy "photos upload own today" on storage.objects for insert
  with check (bucket_id = 'photos' and (storage.foldername(name))[1] = auth.uid()::text
              and (storage.foldername(name))[2] >= public.ritmo_today(auth.uid())::text);
drop policy if exists "photos delete own today" on storage.objects;
create policy "photos delete own today" on storage.objects for delete
  using (bucket_id = 'photos' and (storage.foldername(name))[1] = auth.uid()::text
         and (storage.foldername(name))[2] >= public.ritmo_today(auth.uid())::text);
