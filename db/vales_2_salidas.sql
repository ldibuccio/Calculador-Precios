do $$
begin
  if to_regclass('vales_a_cobrar_salidas') is not null then
    raise exception 'vales_a_cobrar_salidas ya existe: este bloque ya corrio';
  end if;
  create table vales_a_cobrar_salidas (
    vale_id bigint primary key references vales_a_cobrar (id),
    tipo text not null check (tipo in ('cobrado', 'cruzado', 'anulado')),
    fecha date not null,
    importe_cobrado numeric(14, 2),
    ingreso_a_caja text,
    referencia text,
    motivo text,
    sector text not null check (sector in ('administracion', 'gerencia')),
    creado_en timestamptz not null default now(),
    constraint vales_salida_cobrado check (tipo <> 'cobrado'
      or (coalesce(importe_cobrado > 0, false) and sector = 'administracion')),
    constraint vales_salida_cruzado check (tipo <> 'cruzado'
      or (btrim(coalesce(referencia, '')) <> '' and sector = 'administracion')),
    constraint vales_salida_anulado check (tipo <> 'anulado'
      or (btrim(coalesce(motivo, '')) <> '' and sector = 'gerencia')),
    constraint vales_salida_campos_de_su_tipo check (
      (tipo = 'cobrado' or (importe_cobrado is null and ingreso_a_caja is null))
      and (tipo = 'cruzado' or referencia is null)
      and (tipo = 'anulado' or motivo is null))
  );
  comment on table vales_a_cobrar_salidas is
    'Por donde salio un vale de la cartera: cobrado, cruzado con el proveedor '
    'o anulado. UNA por vale (la clave es vale_id). Sector y hora dicen quien.';
end $$;

-- VALES A COBRAR (duenio, 30/09), bloque 2 de 4: las salidas.
--
-- Cobrado y cruzado son de Administracion; anulado es SOLO de Gerencia y con
-- motivo. La base lo hace cumplir con el sector: la pantalla es la forma
-- comoda, la pared es esta.
--
-- Un vale sin fila aca esta EN CARTERA. Una sola salida por vale: cobrar dos
-- veces el mismo vale lo rebota la clave primaria.
--
-- Se corre despues de vales_1, SOLO. Verificacion: vales_5_verificacion.sql.
