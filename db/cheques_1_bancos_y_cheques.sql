-- CARTERA DE CHEQUES (dueño, 13/10), bloque 1 de 5. Corrido por Lionel en Frutamax y Palmala el 13/10.
do $$
begin
  create table if not exists bancos (
    id        bigint generated always as identity primary key,
    nombre    text not null check (btrim(nombre) <> ''),
    creado_en timestamptz not null default now()
  );
  create unique index if not exists bancos_nombre_unico on bancos (upper(btrim(nombre)));
  alter table bancos enable row level security;

  create table if not exists cheques (
    id            bigint generated always as identity primary key,
    numero        text not null check (btrim(numero) <> ''),
    banco_id      bigint not null references bancos (id),
    tipo          text not null check (tipo in ('fisico', 'echeq')),
    fecha_carga   date not null,
    fecha_pago    date not null,
    importe       numeric(14, 2) not null check (importe > 0),
    origen        text not null check (origen in ('cliente', 'a_mano', 'canje')),
    cliente_id    bigint references clientes (id),
    nombre_a_mano text,
    cuit_librador text not null check (cuit_librador ~ '^[0-9]{11}$'),
    sector        text not null check (sector = 'gerencia'),
    creado_en     timestamptz not null default now(),
    constraint cheques_origen_coherente check (
      (origen = 'cliente' and cliente_id is not null and nombre_a_mano is null)
      or (origen = 'a_mano' and cliente_id is null
          and coalesce(btrim(nombre_a_mano) <> '', false))
      or (origen = 'canje' and cliente_id is null and nombre_a_mano is null))
  );
  create unique index if not exists cheques_banco_numero_librador
    on cheques (banco_id, ltrim(upper(btrim(numero)), '0'), cuit_librador);
  create index if not exists cheques_por_cliente on cheques (cliente_id);
  create index if not exists cheques_por_fecha_pago on cheques (fecha_pago);
  alter table cheques enable row level security;
end $$;
