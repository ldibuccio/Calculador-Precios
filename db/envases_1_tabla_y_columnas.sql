do $$
begin
  if not exists (select 1 from information_schema.columns
                  where table_name = 'envases' and column_name = 'umbral_reposicion') then
    alter table envases add column umbral_reposicion integer;
  end if;

  create table if not exists movimientos_envase (
      id              bigint generated always as identity primary key,
      envase_id       bigint not null references envases (id),
      origen          text not null,
      cantidad        integer not null,
      motivo          text,
      fecha_operacion date not null,
      stock_sistema   integer not null,
      creado_en       timestamptz not null default now(),
      anulado_el      timestamptz
  );

  create unique index if not exists movimientos_envase_un_conteo_inicial
      on movimientos_envase (envase_id)
      where origen = 'conteo_inicial' and anulado_el is null;

  create index if not exists movimientos_envase_stock_idx
      on movimientos_envase (envase_id, fecha_operacion)
      where anulado_el is null;

  if not exists (select 1 from information_schema.columns
                  where table_name = 'movimientos_envase' and column_name = 'stock_sistema') then
    raise exception 'movimientos_envase quedo sin stock_sistema: el bloque no se aplico entero';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 1 de 5 del stock de cajas. CORRE SOLO, y la verificacion
-- (envases_6) va en OTRA corrida: pegados, el editor se queda con la ultima
-- y el `do` NO SE EJECUTA.
--
-- `movimientos_envase` guarda SOLO lo que declara una persona: el conteo
-- fisico inicial, la compra de cajas, el prestamo de vacias al puesto y el
-- ajuste. Lo automatico NO SE ESCRIBE ACA, se deriva de la guia R y del
-- reingreso por rechazo — dos caminos al mismo hecho es la regla escrita
-- dos veces, y el que quedara viejo desconectaria el stock sin avisar.
--
-- `stock_sistema` es la foto del momento, igual que en ajustes_vacios y en
-- movimientos_stock: un ajuste que pudiera pisar el stock sin dejar rastro
-- tapa cualquier faltante y se acaba el control cruzado.
--
-- El indice unico parcial es el que impide DOS conteos iniciales vigentes
-- del mismo envase: son la base de la cuenta, y dos duplican el stock.
--
-- `umbral_reposicion` nullable = ese envase no se vigila.
