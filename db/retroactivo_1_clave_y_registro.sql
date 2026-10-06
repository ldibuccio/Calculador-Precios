do $$
begin
  if to_regclass('public.retroactivos') is not null then
    raise exception 'retroactivo_1 ya corrio';
  end if;
  create table claves_especiales (
    nombre text primary key check (nombre in ('retroactivo')),
    sal text not null check (btrim(sal) <> ''),
    hash text not null check (btrim(hash) <> ''),
    cambiada_el timestamptz not null default now()
  );
  create table retroactivos (
    id bigint generated always as identity primary key,
    tipo text not null check (tipo in ('ingreso', 'devolucion', 'merma', 'pase_a_segunda')),
    fecha_del_hecho date not null,
    quien text not null check (btrim(quien) <> ''),
    cargado_el timestamptz not null default now(),
    compra_id bigint references compras (id) on delete cascade,
    movimiento_id bigint references movimientos_stock (id),
    constraint retroactivos_a_que_apunta check (
      (tipo = 'ingreso' and compra_id is not null and movimiento_id is null)
      or (tipo <> 'ingreso' and movimiento_id is not null and compra_id is null))
  );
end $$;

-- RETROACTIVO DESDE ADMINISTRACION (dueño, 05/10): la contraseña
-- especial (solo su hash con sal; se fija desde Gerencia) y el registro de
-- lo cargado con fecha anterior: quien y cuando. Si se corre dos veces,
-- da error y no escribe nada. Verificacion APARTE:
-- retroactivo_1_verificacion.sql.
