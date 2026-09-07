-- DOS cosas de una, por ficha, para las que hay que declarar al corte:
-- 1) COMO SE LLAMA EN EL PISO, para que el deposito sepa que contar.
-- 2) El costo REAL de esas cajas: sale de las guias R de esa misma ficha
--    ANTERIORES al corte, que son las que las armaron. Eso no es un proxy
--    —es el costo congelado de esas cajas—, a diferencia del promedio de
--    las guias R posteriores, que son otra mercaderia de otros dias.
-- Cambiar la lista de ficha_id por las que devolvio corte_fifo_8.
with c0 as (select fecha from corte_modelo where id = 1),
objetivo(ficha_id) as (values (15),(2),(7),(16),(13),(3),(9),(1),(11),(12),(5)),
previas as (
 select rp.ficha_id fid,
  sum(rp.costo_total) as pl, sum(rp.bultos_primera) as bl,
  max(rp.fecha_operacion) as ultima,
  count(*) as guias
 from reprocesos rp
 where rp.anulado_el is null and rp.tipo = 'normal'
   and rp.fecha_operacion < (select fecha from c0)
   and rp.costo_total is not null and rp.bultos_primera > 0
 group by 1
)
select o.ficha_id,
 a.nombre as articulo,
 cl.nombre as cliente,
 coalesce(e.nombre, 'sin envase') as envase,
 f.contenido_caja as contenido,
 f.unidad_venta as unidad,
 case when f.envase_variable then 'SI' else '' end as envase_variable,
 f.nombre_cliente, f.codigo_cliente,
 round(p.pl / nullif(p.bl, 0), 2) as costo_previo,
 p.guias as guias_previas,
 p.ultima as ultima_previa
from objetivo o
join fichas_logistica f on f.id = o.ficha_id
join articulos a on a.id = f.articulo_id
join clientes cl on cl.id = f.cliente_id
left join envases e on e.id = f.envase_id
left join previas p on p.fid = o.ficha_id
order by a.nombre;
