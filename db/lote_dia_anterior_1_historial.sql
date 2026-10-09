do $$
begin
  if to_regclass('public.pedidos_renglones_lotes_correcciones') is not null then
    raise exception 'lote_dia_anterior_1 ya corrio';
  end if;
  create table pedidos_renglones_lotes_correcciones (
    id bigint generated always as identity primary key,
    renglon_id bigint not null references pedidos_renglones (id) on delete cascade,
    quien text not null,
    corregido_el timestamptz not null default now(),
    antes jsonb not null,
    ahora jsonb not null,
    costo_antes numeric,
    costo_ahora numeric,
    constraint lotes_correcciones_con_quien check (btrim(quien) <> '')
  );
  create index lotes_correcciones_por_renglon
    on pedidos_renglones_lotes_correcciones (renglon_id);
  alter table pedidos_renglones_lotes_correcciones enable row level security;
end $$;

-- DE QUE LOTE SALIO UN PEDIDO DE UN DIA ANTERIOR (dueño, 09/10): el
-- historial de cada correccion hecha desde Administracion con la
-- contrasena especial: quien, cuando, de donde salia antes, de donde sale
-- ahora y el costo de antes y de ahora. Nace con candado (RLS), sin
-- politicas. Si se corre dos veces, da error y no escribe nada.
-- Verificacion APARTE: lote_dia_anterior_1_verificacion.sql.
