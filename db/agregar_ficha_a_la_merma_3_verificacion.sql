-- MERMA POR FICHA (bloque 3 de 3): qué quedó escrito. Se corre DESPUÉS.
--
-- CONTEOS y no una lista: con conteos siempre vuelve una fila y el cero se
-- ve; con una lista, "todo bien" y "no corrió" son la misma pantalla vacía.
--
-- Y cada constraint se cuenta POR NOMBRE. Un "¿existe algún check?" daría 1
-- por los que ya estaban y taparía que el nuevo no se creó — que es como se
-- descubrió el 09/09 que un bloque idempotente no había hecho nada.
--
-- Los cuatro tienen que dar 1. `mermas_con_ficha` va a dar 0 hoy y está
-- bien: la columna nace vacía y la pantalla todavía no la escribe. Al lado
-- va `ultima_merma` como testigo: sin él, un 0 de "no se cargó ninguna" se
-- lee igual que un 0 de "acá no pasa nada".
select
    (select count(*) from information_schema.columns
      where table_name = 'movimientos_stock' and column_name = 'ficha_id')   as columna,
    (select count(*) from pg_constraint
      where conname = 'fichas_logistica_id_articulo_unico')                  as unico,
    (select count(*) from pg_constraint
      where conname = 'movimientos_stock_ficha_del_articulo')                as fk_compuesta,
    (select count(*) from pg_constraint
      where conname = 'movimientos_stock_ficha_solo_merma')                  as guarda_solo_merma,
    (select count(*) from movimientos_stock
      where ficha_id is not null and anulado_el is null)                     as mermas_con_ficha,
    (select count(*) from movimientos_stock
      where tipo <> 'merma' and ficha_id is not null)                        as ofensores_otro_tipo,
    (select max(fecha_operacion) from movimientos_stock
      where tipo = 'merma' and anulado_el is null)                           as ultima_merma;
