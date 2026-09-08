-- ¿HAY MAILS "Confirmado" QUE NO HAYAN PRODUCIDO UN PEDIDO VIVO?
-- Un mail confirmado que no produjo pedido es peor que uno pendiente: el
-- cartel dice que esta resuelto y no lo esta.
-- Los dos caminos que confirman (la revision a mano y el auto-confirmado)
-- marcan el mail SOLO despues de que crear_pedido devolvio un id, asi que
-- sin_pedido_id tendria que dar 0. Si no da 0, hay un camino que no
-- conocemos y eso es lo primero a mirar.
-- pedido_anulado SI puede pasar y no siempre es un problema: un pedido
-- corregido se reemplaza y el viejo queda anulado, con el mail apuntando
-- al viejo. Lo que importa es que el mail tenga UNA cadena que termine en
-- un pedido vivo; si el anulado no fue reemplazado, ahi si falta.
-- no_vigente_en_su_fecha: el pedido esta vivo pero otro mas nuevo del mismo
-- cliente y fecha le gana por creado_en, asi que no lo arma nadie. Es la
-- misma regla que usan las siete consultas del FIFO.
-- Conteos y no lista: con lista, "no hay ninguno" y "no corrio" son la
-- misma pantalla vacia. ultimo_confirmado es el testigo de actividad.
select count(*) confirmados,
  count(*) filter (where m.pedido_id is null) sin_pedido_id,
  count(*) filter (where p.id is not null and p.anulado_el is not null) pedido_anulado,
  count(*) filter (where p.id is not null and p.anulado_el is not null
    and not exists (select 1 from pedidos nuevo
                    where nuevo.reemplaza_a_pedido_id = p.id)) anulado_sin_reemplazo,
  count(*) filter (where p.anulado_el is null and p.id is not null
    and p.id <> (select p2.id from pedidos p2
                 where p2.cliente_id = p.cliente_id
                   and p2.fecha_operacion = p.fecha_operacion
                   and p2.anulado_el is null
                 order by p2.creado_en desc limit 1)) no_vigente_en_su_fecha,
  count(*) filter (where p.anulado_el is null and p.id is not null) pedido_vivo,
  max((m.procesado_el at time zone 'America/Argentina/Buenos_Aires')::date) ultimo_confirmado
from mails_pedido m
left join pedidos p on p.id = m.pedido_id
where m.estado = 'confirmado';
