-- VERIFICACION de la marca "viene armada en caja nuestra" en la compra.
-- Esperado en una base que todavia no la usa: 1 · 1 · 0 · 0 + poblacion y testigo.
select
  (select count(*) from information_schema.columns
    where table_schema='public' and table_name='compras'
      and column_name='ficha_en_origen_id')                         as col_ficha_en_origen,
  (select count(*) from pg_indexes
    where schemaname='public' and indexname='compras_ficha_en_origen_idx') as indice,
  (select count(*) from compras where ficha_en_origen_id is not null)      as compras_marcadas,
  -- Las que ya se recepcionaron y TODAVIA no tienen su guia: es la cola que
  -- la salida de Buscar Compras tiene que mostrar. Cero es lo esperado hoy.
  (select count(*) from compras c
    where c.ficha_en_origen_id is not null and c.estado='recepcionado'
      and not exists (select 1 from reprocesos r
                      where r.compra_origen_id=c.id and r.anulado_el is null)) as marcadas_sin_guia,
  -- La POBLACION al lado del conteo, y el TESTIGO de actividad: un cero sobre
  -- una base parada no vota (en Palmala la ultima recepcion va a estar vieja).
  (select count(*) from compras where estado='recepcionado')          as compras_recepcionadas,
  (select max(procesada_el)::date from compras)                       as ultima_recepcion;
