do $$
begin
  if to_regclass('vales_a_cobrar_limites') is not null then
    raise exception 'vales_a_cobrar_limites ya existe: este bloque ya corrio';
  end if;
  create table vales_a_cobrar_limites (
    id integer primary key check (id = 1),
    monto numeric(14, 2) not null check (monto > 0),
    dias integer not null check (dias > 0),
    actualizado_en timestamptz not null default now()
  );
  insert into vales_a_cobrar_limites (id, monto, dias) values (1, 500000, 14);
  comment on table vales_a_cobrar_limites is
    'Los dos limites de las alertas de vales: plata en cartera y dias sin '
    'aplicar. UNA fila. Se editan con la clave de Gerencia.';
end $$;

-- VALES A COBRAR (duenio, 30/09), bloque 3 de 4: los limites de las alertas.
-- Arrancan en $500.000 y 14 dias (duenio). Las columnas NO tienen default: el
-- valor inicial esta escrito una vez, en este insert.
--
-- Se corre despues de vales_2, SOLO. Verificacion: vales_5_verificacion.sql.
