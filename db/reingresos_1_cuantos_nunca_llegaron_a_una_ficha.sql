-- ¿Cuántos reingresos por rechazo quedaron fuera de la cuenta por ficha, y
-- cuántos bultos son? Solo lectura. CORRER EN LAS DOS BASES.
--
-- Por qué TODOS y no solo los rotos: _SQL_STOCK_PARTIDO no lee
-- movimientos_stock, así que NINGÚN reingreso entró nunca en una ficha.
-- Lo que se mide acá no es cuántos fallaron: es cuántos habría que mover
-- si se arregla, que es otra pregunta.
--
-- La partición es por si el dato ALCANZA para atribuirlo:
--   con_ficha  -> tiene pedido_renglon_id y ese renglón tiene ficha_id.
--                 Estos se pueden reatribuir sin pedirle nada a nadie.
--   sin_ficha  -> tiene renglón pero el renglón no tiene ficha.
--   sin_vinculo-> no tiene pedido_renglon_id (cargado a mano, o viejo).
-- Los dos últimos NO se pueden arreglar solos aunque se cambie la cuenta.
--
-- ultima_recepcion es el TESTIGO DE ACTIVIDAD: en una base parada estos
-- ceros no dicen que esté todo bien, dicen que no hubo nada que contar.
select
  count(*)                                                          as reingresos,
  count(*) filter (where pr.ficha_id is not null)                   as con_ficha,
  count(*) filter (where m.pedido_renglon_id is not null
                     and pr.ficha_id is null)                       as sin_ficha,
  count(*) filter (where m.pedido_renglon_id is null)               as sin_vinculo,
  coalesce(sum(m.cantidad), 0)                                      as bultos,
  coalesce(sum(m.cantidad) filter (where pr.ficha_id is not null), 0) as bultos_con_ficha,
  count(distinct m.articulo_id)                                     as articulos,
  min(m.fecha_operacion)                                            as desde,
  max(m.fecha_operacion)                                            as hasta,
  (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion
from movimientos_stock m
left join pedidos_renglones pr on pr.id = m.pedido_renglon_id
where m.anulado_el is null
  and m.tipo = 'reingreso_rechazo'
  and (m.destino_rechazo is null or m.destino_rechazo = 'stock');
