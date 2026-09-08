-- EL DETALLE de los mails de los ultimos 10 dias, con el pedido que
-- produjeron. Es la que contesta "que paso con ESTE mail":
--   estado          lo que dice el cartel de la casilla.
--   pedido_id       null = no produjo pedido (no deberia pasar).
--   fecha_pedido    CON QUE FECHA quedo. "Pedidos para armar" muestra UNA
--                   fecha por vez, asi que un pedido del 09 no se ve
--                   mirando el 08 -- y parece que no existe.
--   anulado         el pedido esta dado de baja.
--   vigente         es el que el deposito arma ese dia (misma regla que el
--                   FIFO: el mas nuevo por creado_en de ese cliente+fecha).
--   dias            fecha del pedido menos dia de llegada del mail. El
--                   asunto manda la fecha y el mail del mediodia es para el
--                   dia siguiente, asi que 1 es lo normal.
select (m.recibido_el at time zone 'America/Argentina/Buenos_Aires')::date llego,
  m.id mail, m.estado, m.asunto,
  m.pedido_id, p.fecha_operacion fecha_pedido,
  p.anulado_el is not null anulado,
  (p.id = (select p2.id from pedidos p2
           where p2.cliente_id = p.cliente_id
             and p2.fecha_operacion = p.fecha_operacion
             and p2.anulado_el is null
           order by p2.creado_en desc limit 1)) vigente,
  p.fecha_operacion - (m.recibido_el at time zone 'America/Argentina/Buenos_Aires')::date dias,
  (select count(*) from pedidos_renglones r
   where r.pedido_id = p.id and r.anulado_el is null) renglones
from mails_pedido m
left join pedidos p on p.id = m.pedido_id
where m.recibido_el >= ((current_date - 10)::timestamp
                        at time zone 'America/Argentina/Buenos_Aires')
order by m.recibido_el desc;
