-- listados_compra_1_cabecera.sql — CORRIDO Y CONFIRMADO en las dos bases el 21/09.
do $$
begin
  if not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                 where c.relname = 'listados_compra' and n.nspname = 'public') then
    create table listados_compra (
        id                 bigint generated always as identity primary key,
        fecha              date not null,
        estado             text not null,
        margen_porcentaje  numeric not null,
        creado_en          timestamptz not null default now(),
        actualizado_en     timestamptz not null default now()
    );
  end if;
end $$;

alter table listados_compra drop constraint if exists listados_compra_estado_check;
alter table listados_compra add constraint listados_compra_estado_check
    check (estado in ('borrador', 'cerrado'));

alter table listados_compra drop constraint if exists listados_compra_margen_check;
alter table listados_compra add constraint listados_compra_margen_check
    check (margen_porcentaje >= 0);

create unique index if not exists listados_compra_un_borrador_por_dia_idx
    on listados_compra (fecha) where estado = 'borrador';

comment on table listados_compra is 'Cabecera de un "Que comprar hoy". borrador = se sigue editando parado en el Mercado; cerrado = queda como historial de lo que se salio a comprar ese dia.';
comment on column listados_compra.margen_porcentaje is 'Cuanto se compra de mas, en por ciento, SOBRE LO QUE PIDEN y no sobre el faltante: el margen existe porque lo que se va a vender es incierto, y el piso esta contado. SIN DEFAULT a proposito: el valor de arranque lo propone la pantalla (MARGEN_SUGERIDO, core/que_comprar.py) y dos defaults que no coinciden es como se separan dos reglas. 0 significa sin margen.';
