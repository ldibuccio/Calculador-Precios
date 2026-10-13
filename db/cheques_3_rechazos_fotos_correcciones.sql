-- CARTERA DE CHEQUES (dueño, 13/10), bloque 3 de 5. Corrido por Lionel en Frutamax y Palmala el 13/10.
do $$
begin
  create table if not exists cheques_rechazos (
    cheque_id   bigint primary key references cheques (id),
    fecha       date not null,
    motivo      text not null check (btrim(motivo) <> ''),
    sector      text not null check (sector = 'gerencia'),
    creado_en   timestamptz not null default now(),
    resuelto_el date,
    resolucion  text check (resolucion is null or btrim(resolucion) <> ''),
    constraint cheques_rechazos_resuelto_coherente
      check ((resuelto_el is null) = (resolucion is null)),
    constraint cheques_rechazos_resuelto_despues
      check (resuelto_el is null or resuelto_el >= fecha)
  );
  alter table cheques_rechazos enable row level security;

  create table if not exists cheques_fotos (
    id        bigint generated always as identity primary key,
    cheque_id bigint not null references cheques (id),
    lado      text not null check (lado in ('frente', 'dorso')),
    foto_ruta text not null unique check (btrim(foto_ruta) <> ''),
    sector    text not null check (sector = 'gerencia'),
    creado_en timestamptz not null default now()
  );
  create index if not exists cheques_fotos_por_cheque on cheques_fotos (cheque_id);
  alter table cheques_fotos enable row level security;

  create table if not exists cheques_correcciones (
    id             bigint generated always as identity primary key,
    cheque_id      bigint not null references cheques (id),
    campo          text not null check (campo in ('numero', 'banco', 'tipo', 'fecha_carga',
                     'fecha_pago', 'importe', 'origen', 'cliente', 'nombre_a_mano',
                     'cuit_librador')),
    valor_anterior text,
    valor_nuevo    text,
    sector         text not null check (sector = 'gerencia'),
    creado_en      timestamptz not null default now(),
    constraint cheques_correcciones_distinto
      check (valor_anterior is distinct from valor_nuevo)
  );
  create index if not exists cheques_correcciones_por_cheque
    on cheques_correcciones (cheque_id);
  alter table cheques_correcciones enable row level security;
end $$;
