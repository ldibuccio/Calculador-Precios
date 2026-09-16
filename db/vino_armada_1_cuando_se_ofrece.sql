-- CUÁNDO SE OFRECE "Vino armada" EN BUSCAR COMPRAS, y en cuántos de esos
-- casos la pantalla de destino lo va a rechazar.
--
-- Conteos y no lista: así el cero se ve (una lista vacía y una consulta que
-- no corrió son la misma pantalla). El detalle va en vino_armada_2.
with c0 as (select fecha from corte_modelo where id = 1)
select
  (select fecha from c0)                                        as corte,
  (select max(fecha_operacion) from compras
    where estado = 'recepcionado')                              as ultima_recepcion,
  (select max(fecha_operacion) from reprocesos
    where anulado_el is null)                                   as ultima_guia_r,
  count(*)                                                      as ofrecidas,
  count(*) filter (
    where (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
          <= (select fecha from c0))                            as frenaria_el_corte,
  count(*) filter (where c.procesada_el is null)                as sin_fecha_de_lote,
  count(*) filter (where cons.bultos > 0)                       as con_lote_ya_consumido,
  count(*) filter (
    where cons.bultos >= coalesce(c.cantidad_cajones_real, c.cantidad_cajones))
                                                                as con_lote_consumido_entero,
  (select count(*) from compras where estado = 'recepcionado')  as recepcionadas_totales
from compras c
left join lateral (
  select coalesce(sum(rc.bultos), 0) as bultos
    from reprocesos_consumos rc
    join reprocesos r on r.id = rc.reproceso_id
   where rc.origen = 'compra' and rc.compra_id = c.id and r.anulado_el is null
) cons on true
where c.estado = 'recepcionado'
  and c.ficha_en_origen_id is null;
