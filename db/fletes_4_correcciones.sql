do $$
begin
  if to_regclass('fletes_viajes') is null then
    raise exception 'falta fletes_viajes: corre primero fletes_3';
  end if;
  if to_regclass('fletes_correcciones') is not null then
    raise exception 'fletes_correcciones ya existe: este bloque ya corrio';
  end if;
  create table fletes_correcciones (
    id bigint generated always as identity primary key,
    flete_id bigint not null references fletes (id),
    sector text not null check (sector in ('administracion', 'gerencia')),
    antes jsonb not null,
    despues jsonb not null,
    corregido_el timestamptz not null default now()
  );
  create index fletes_correcciones_por_flete on fletes_correcciones (flete_id);
  create function viaje_pagado_no_se_toca() returns trigger
  language plpgsql as $f$
  begin
    if old.pagado_el is not null then
      raise exception 'el viaje % ya se pago: no se corrige', old.id
        using errcode = 'check_violation', constraint = 'viaje_pagado_no_se_toca';
    end if;
    return case when tg_op = 'DELETE' then old else new end;
  end $f$;
  create trigger viaje_pagado_no_se_toca
    before update or delete on fletes_viajes
    for each row execute function viaje_pagado_no_se_toca();
end $$;

-- FLETES, bloque 4 de 4: las correcciones, con historial.
--
-- Un flete se corrige el mismo dia desde Administracion; despues, solo desde
-- Gerencia. Cada correccion guarda como estaba y como quedo. Un viaje ya
-- pagado no se cambia ni se borra: lo decide la base (el codigo traduce el
-- error), igual que un vale que salio.
