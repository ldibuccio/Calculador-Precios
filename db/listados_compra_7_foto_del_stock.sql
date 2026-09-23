do $$
begin
  if not exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = 'listados_compra'
                    and column_name = 'generado_el') then
    alter table listados_compra add column generado_el timestamptz;
  end if;

  create table if not exists listados_compra_foto (
      listado_id        bigint not null references listados_compra (id) on delete cascade,
      articulo_id       bigint not null references articulos (id),
      sueltos           numeric not null,
      sueltos_magnitud  numeric,
      primary key (listado_id, articulo_id)
  );

  create table if not exists listados_compra_foto_cajas (
      listado_id   bigint not null references listados_compra (id) on delete cascade,
      ficha_id     bigint not null references fichas_logistica (id),
      articulo_id  bigint not null references articulos (id),
      cajas        numeric not null,
      magnitud     numeric,
      primary key (listado_id, ficha_id)
  );
end $$;

comment on column listados_compra.generado_el is 'CUANDO SE APRETO "SALGO A COMPRAR" (dueno, 23/09). Es el punto de partida del listado: la foto del stock se saca en ese instante, lo comprado es lo que se cargo DESPUES, y lo en camino lo que se cargo ANTES y todavia no se habia recepcionado. NULL = todavia no se salio. No es creado_en: armar la lista y salir pueden ser momentos distintos.';
comment on table listados_compra_foto is 'LA FOTO DEL STOCK al apretar "Salgo a comprar", por articulo: los SUELTOS en bultos y en la magnitud de la fila (NULL si las pilas no cierran). Se guarda porque el stock se cuenta por DIA y no por hora: el de las 22 no se puede recalcular despues.';
comment on table listados_compra_foto_cajas is 'La otra mitad de la foto: las CAJAS ARMADAS de cada ficha en ese instante, con su magnitud (NULL si la ficha no dice contenido). Por ficha y no por cliente: el listado suma solo las fichas de los clientes tildados, y se pueden tildar despues de salir.';

-- Bloque 1 de 2 del listado atado al momento de salir. Solo AGREGA: una
-- columna nullable y dos tablas que el código de hoy no lee, así que corre
-- ya. El bloque 2 (un solo listado abierto a la vez) va DESPUES del deploy:
-- el código de hoy abre uno por día y el índice nuevo lo haría rebotar.
-- La verificación va en listados_compra_7_verificacion.sql y se corre APARTE.
