-- Guías R sin ficha asignada DESDE EL CORTE (antes del corte el NULL
-- significa otra cosa: dato viejo que no se completa). Parte las que
-- quedaron sin asignar según si HABÍA una ficha para elegir: sin ninguna
-- ficha del cliente para ese artículo, "Sin asignar" no fue una omisión,
-- era la única opción posible.
with corte as (select fecha from corte_modelo where id = 1)
select rp.id as guia, rp.fecha_operacion, a.nombre as articulo,
       coalesce(cl.nombre, 'SIN CLIENTE') as cliente,
       rp.bultos_primera, rp.tipo,
       (select count(*) from fichas_logistica f
         where f.articulo_id = rp.articulo_id
           and f.cliente_id is not distinct from rp.cliente_id) as fichas_que_habia,
       case
         when rp.cliente_id is null then 'sin cliente: no hay a quien pedirle ficha'
         when not exists (select 1 from fichas_logistica f
                           where f.articulo_id = rp.articulo_id
                             and f.cliente_id = rp.cliente_id)
              then 'NO HABIA FICHA para elegir'
         else 'habia ficha y no se eligio'
       end as motivo
from reprocesos rp
join articulos a on a.id = rp.articulo_id
left join clientes cl on cl.id = rp.cliente_id
where rp.ficha_id is null
  and rp.anulado_el is null
  and rp.bultos_primera > 0
  and rp.fecha_operacion >= (select fecha from corte)
order by rp.fecha_operacion desc, rp.id desc;
