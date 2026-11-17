-- Un día puede tener una segunda foto: dia-NN-2.jpg, junto a dia-NN.jpg.
-- Bea la ve con la misma regla que la primera: solo cuando ya ha llegado su día.

drop policy "ver la foto de un día que ya ha llegado" on storage.objects;

create policy "ver la foto de un día que ya ha llegado"
  on storage.objects for select
  to authenticated
  using (
    bucket_id = 'fotos'
    and (
      (select public.rol_actual()) = 'admin'
      or (
        (select public.rol_actual()) = 'bea'
        and name ~ '^dia-\d{2}(-2)?\.jpg$'
        and public.dia_desbloqueado(substring(name from '^dia-(\d{2})')::int)
      )
    )
  );
