-- ############################################################################
-- CUÁNTO QUEDA VIVO DEL LOTE FANTASMA. Solo lectura, no escribe nada.
--
-- `lotes_fantasma_del_compensatorio.sql` mide el TAMAÑO del compensatorio (lo
-- que se escribió el día del corte). Esto mide lo que TODAVÍA NO SE CONSUMIÓ,
-- que es otra cosa y es la que decide qué pasa el lunes.
--
-- Por qué se puede calcular en SQL, si el FIFO se reparte en Python: el
-- compensatorio POSITIVO existe justo porque el artículo estaba en NEGATIVO, y
-- un artículo en negativo no tiene ningún lote con resto. O sea que el
-- compensatorio es SIEMPRE el lote más viejo disponible en su fecha, y lo
-- primero que consume cualquier salida posterior.
--
-- Se mira solo el compensatorio MÁS NUEVO de cada artículo: si hubo uno
-- después, el de antes ya estaba consumido (por lo mismo de arriba).
-- ############################################################################
with ultimo as (
  select articulo_id, max(fecha_operacion) fecha
  from movimientos_stock
  where anulado_el is null and tipo = 'cierre_modelo_viejo' and cantidad > 0
  group by 1
), lote as (
  select u.articulo_id, u.fecha, sum(m.cantidad) bultos
  from ultimo u
  join movimientos_stock m on m.articulo_id = u.articulo_id
   and m.fecha_operacion = u.fecha and m.tipo = 'cierre_modelo_viejo'
   and m.anulado_el is null and m.cantidad > 0
  group by 1, 2
), vigentes as (
  select distinct on (cliente_id, fecha_operacion) id, fecha_operacion
  from pedidos where anulado_el is null
  order by cliente_id, fecha_operacion, creado_en desc
)
select a.nombre articulo, l.fecha, l.bultos lote_fantasma, s.salidas,
       greatest(l.bultos - s.salidas, 0) restante,
       (select round(avg(rp.bultos_tomados), 1) from reprocesos rp
        where rp.articulo_id = l.articulo_id and rp.anulado_el is null
          and rp.fecha_operacion > l.fecha - 30) promedio_guia_r
from lote l
join articulos a on a.id = l.articulo_id
cross join lateral (
  select coalesce((select sum(coalesce(r.cantidad_armada, r.cantidad))
                   from pedidos_renglones r join vigentes v on v.id = r.pedido_id
                   where r.articulo_id = l.articulo_id and r.anulado_el is null
                     and r.armado_el is not null
                     and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date > l.fecha), 0)
       + coalesce((select sum(-m.cantidad) from movimientos_stock m
                   where m.articulo_id = l.articulo_id and m.anulado_el is null
                     and m.cantidad < 0 and m.fecha_operacion > l.fecha), 0)
       + coalesce((select sum(rp.bultos_tomados) from reprocesos rp
                   where rp.articulo_id = l.articulo_id and rp.anulado_el is null
                     and rp.fecha_operacion > l.fecha), 0) salidas
) s
order by 5 desc, 1;
