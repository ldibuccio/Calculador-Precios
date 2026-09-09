-- BLOQUE 4 — verificación. CONTEOS y no una lista: siempre vuelve una fila y
-- el cero se ve. Esperado en las dos bases: 1, 1, 1, ofensores 0, y todas
-- las salidas viejas en 'puesto' (que es lo que eran).
--
-- `ultima_salida` es el TESTIGO DE ACTIVIDAD: sin él, una base sin un solo
-- remito devuelve todo en cero y el cero se lee como éxito.
select
    (select count(*) from information_schema.columns
      where table_schema = 'public' and table_name = 'remitos_segunda'
        and column_name = 'destino')                                  as columna_destino,
    (select count(*) from pg_constraint
      where conname = 'remitos_segunda_motivo_solo_merma')            as guarda_coherencia,
    (select count(*) from pg_constraint
      where conname = 'remitos_segunda_motivo_de_la_lista')           as guarda_lista,
    (select count(*) from remitos_segunda)                            as salidas_totales,
    (select count(*) from remitos_segunda where destino = 'puesto')   as al_puesto,
    (select count(*) from remitos_segunda where destino = 'merma')    as mermas,
    (select count(*) from remitos_segunda
      where (destino = 'merma') <> (motivo is not null))              as ofensores,
    (select max(fecha_operacion) from remitos_segunda
      where anulado_el is null)                                       as ultima_salida;
