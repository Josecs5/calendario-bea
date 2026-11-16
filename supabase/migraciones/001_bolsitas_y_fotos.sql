-- Calendario de Bea: bolsitas abiertas por cuenta y almacén privado de fotos.
-- Toda regla exige un rol puesto a mano en app_metadata ('bea' o 'admin'),
-- así que una cuenta creada por cualquier otro no puede ver ni guardar nada.

create or replace function public.rol_actual()
returns text
language sql
stable
security invoker
set search_path = ''
as $$
  select auth.jwt() -> 'app_metadata' ->> 'rol'
$$;

-- El día N (1–24) se desbloquea a las 00:00 de Madrid del N de diciembre de 2026.
create or replace function public.dia_desbloqueado(dia int)
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select dia between 1 and 24
     and now() >= make_timestamptz(2026, 12, dia, 0, 0, 0, 'Europe/Madrid')
$$;

create table public.bolsitas_abiertas (
  user_id uuid not null references auth.users (id) on delete cascade default auth.uid(),
  dia smallint not null check (dia between 1 and 24),
  abierta_en timestamptz not null default now(),
  primary key (user_id, dia)
);

alter table public.bolsitas_abiertas enable row level security;

create policy "ver mis bolsitas"
  on public.bolsitas_abiertas for select
  to authenticated
  using (user_id = (select auth.uid()));

create policy "abrir bolsitas de días que ya han llegado"
  on public.bolsitas_abiertas for insert
  to authenticated
  with check (
    user_id = (select auth.uid())
    and (select public.rol_actual()) in ('bea', 'admin')
    and ((select public.rol_actual()) = 'admin' or public.dia_desbloqueado(dia))
  );

-- Almacén privado de fotos: dia-01.jpg … dia-24.jpg
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos', 'fotos', false, 5242880, array['image/jpeg']);

create policy "ver la foto de un día que ya ha llegado"
  on storage.objects for select
  to authenticated
  using (
    bucket_id = 'fotos'
    and (
      (select public.rol_actual()) = 'admin'
      or (
        (select public.rol_actual()) = 'bea'
        and name ~ '^dia-\d{2}\.jpg$'
        and public.dia_desbloqueado(substring(name from '^dia-(\d{2})\.jpg$')::int)
      )
    )
  );

create policy "solo admin sube fotos"
  on storage.objects for insert
  to authenticated
  with check (bucket_id = 'fotos' and (select public.rol_actual()) = 'admin');

create policy "solo admin cambia fotos"
  on storage.objects for update
  to authenticated
  using (bucket_id = 'fotos' and (select public.rol_actual()) = 'admin')
  with check (bucket_id = 'fotos' and (select public.rol_actual()) = 'admin');

create policy "solo admin borra fotos"
  on storage.objects for delete
  to authenticated
  using (bucket_id = 'fotos' and (select public.rol_actual()) = 'admin');
