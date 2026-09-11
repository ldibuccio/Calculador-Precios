-- CONTROL DE PEDIDOS (bloque 2 de 2): qué quedó escrito. Se corre DESPUÉS.
--
-- CONTEOS y no una lista: con conteos siempre vuelve una fila y el cero se
-- ve; con una lista, "todo bien" y "no corrió" son la misma pantalla vacía.
-- El constraint se cuenta POR NOMBRE: un "¿existe algún check?" daría 1 por
-- los que ya estaban y taparía que el nuevo no se creó.
--
-- `columna` y `guarda` tienen que dar 1. `controlados` va a dar 0 hoy y
-- está bien: la columna nace vacía y la pantalla todavía no la escribe.
-- `ofensores` tiene que dar 0 SIEMPRE — si diera otra cosa, el CHECK no
-- se creó (no puede haber filas que lo violen con el constraint puesto).
--
-- Al lado van DOS testigos, porque los ceros de arriba no se pueden leer
-- solos: `ultimo_armado` dice si la base arma pedidos, y `renglones_7d`
-- contra cuánto se está contando. En una base quieta los tres ceros son
-- verdaderos y no significan nada.
select
    (select count(*) from information_schema.columns
      where table_name = 'pedidos_renglones' and column_name = 'controlado_el')  as columna,
    (select count(*) from pg_constraint
      where conname = 'pedidos_renglones_controlado_solo_armado')                as guarda,
    (select count(*) from pedidos_renglones
      where controlado_el is not null)                                           as controlados,
    (select count(*) from pedidos_renglones
      where controlado_el is not null and armado_el is null)                     as ofensores,
    (select count(*) from pedidos_renglones r
      join pedidos p on p.id = r.pedido_id
      where p.fecha_operacion > current_date - 7)                                as renglones_7d,
    (select max(armado_el) from pedidos_renglones)                               as ultimo_armado;
