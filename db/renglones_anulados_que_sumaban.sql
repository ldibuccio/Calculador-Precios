-- Qué SACÓ de Rentabilidad de Pedidos el filtro del renglón anulado.
-- Son los renglones que hasta el 07/09 sumaban como vendidos y ya no.
-- "en que seccion estaba": con ficha iba a una fila calculable (y movía la
-- renta); sin ficha iba a "no calculables / sin identificar" (solo bultos).
-- Cambiar los 30 días si querés otra ventana.
with vigentes as (
    select distinct on (cliente_id, fecha_operacion) id, cliente_id, fecha_operacion
    from pedidos
    where anulado_el is null
      and fecha_operacion >= (now() at time zone 'America/Argentina/Buenos_Aires')::date - 30
    order by cliente_id, fecha_operacion, creado_en desc
)
select cl.nombre as cliente, v.fecha_operacion,
       coalesce(a.nombre, r.texto_descripcion, r.texto_codigo, '(sin identificar)') as articulo,
       r.sucursal, r.cantidad as bultos,
       case when r.ficha_id is not null
            then 'fila calculable: movia bultos Y renta'
            else 'no calculables: movia solo bultos' end as en_que_seccion_estaba
from vigentes v
join pedidos_renglones r on r.pedido_id = v.id
join clientes cl on cl.id = v.cliente_id
left join articulos a on a.id = r.articulo_id
where r.anulado_el is not null
order by cl.nombre, v.fecha_operacion desc, articulo;
