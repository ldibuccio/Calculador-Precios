-- ############################################################################
-- LAS FICHAS DE UN ARTÍCULO, CON SUS CAJAS Y SUS SALIDAS. Solo lectura.
--
-- Para saber si un artículo tiene fichas que NUNCA se reprocesan: las que
-- entran ya armadas del proveedor y salen tal cual. Esas fichas tienen
-- producidas = 0 y salidas > 0, o sea un saldo negativo que crece todos los
-- días — y NO es un error: es mercadería que nunca pasó por una guía R.
--
-- NO se filtra por cliente a propósito: filtrar por nombre es justo cómo se
-- pierde la fila que importa. Se listan TODAS las fichas del artículo y el
-- cliente sale en su columna.
--
-- Los pisos son los mismos que usa `_SQL_STOCK_PARTIDO` (cuenta 2): desde el
-- corte, y asimétrico el día del corte. Si acá dijeran otra cosa, los números
-- no serían los que muestra el sistema.
--
-- Cambiar 'cherry' por lo que se quiera mirar.
-- ############################################################################
with corte as (select fecha from corte_modelo where id = 1),
vigentes as (
  select distinct on (cliente_id, fecha_operacion) id
  from pedidos where anulado_el is null
  order by cliente_id, fecha_operacion, creado_en desc
),
objetivo as (select id, nombre from articulos where nombre ilike '%cherry%')
select o.nombre articulo,
       cl.nombre cliente,
       f.id ficha_id,
       coalesce(nullif(btrim(f.nombre_cliente), ''), '(sin nombre propio)') nombre_en_el_pedido,
       f.contenido_caja || ' ' || f.unidad_venta por_caja,
       coalesce(p.total, 0) producidas_por_reproceso,
       coalesce(s.total, 0) salidas_armadas,
       coalesce(p.total, 0) - coalesce(s.total, 0) saldo,
       case when coalesce(p.total, 0) = 0 and coalesce(s.total, 0) > 0
              then 'NUNCA SE REPROCESÓ (viene armada del proveedor)'
            when coalesce(p.total, 0) = 0 then 'sin movimiento'
            else 'se arma en el depósito' end que_es
from objetivo o
join fichas_logistica f on f.articulo_id = o.id
join clientes cl on cl.id = f.cliente_id
left join (
  select r.ficha_id, sum(r.bultos_primera) total
  from reprocesos r, corte
  where r.anulado_el is null and r.ficha_id is not null
    and (r.fecha_operacion > corte.fecha
         or (r.tipo = 'inicial' and r.fecha_operacion >= corte.fecha))
  group by r.ficha_id) p on p.ficha_id = f.id
left join (
  select r.ficha_id, sum(coalesce(r.cantidad_armada, r.cantidad)) total
  from pedidos_renglones r join vigentes v on v.id = r.pedido_id, corte
  where r.armado_el is not null and r.anulado_el is null and r.ficha_id is not null
    and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date > corte.fecha
  group by r.ficha_id) s on s.ficha_id = f.id
order by o.nombre, cl.nombre, f.id;
