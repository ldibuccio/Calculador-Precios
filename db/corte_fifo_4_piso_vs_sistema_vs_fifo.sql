-- Los tres numeros al lado, por articulo, para los SUELTOS (los cajones):
-- lo contado en el piso, lo que el sistema creia en ese mismo instante, y
-- de que lado del corte estan los lotes que respaldan eso.
-- Lo contado y lo del sistema salen de la MISMA fila de conteos_stock, asi
-- que no hay dos definiciones que se puedan separar.
with c0 as (select fecha from corte_modelo where id = 1),
ult as (
 select distinct on (articulo_id) articulo_id, cantidad, stock_sistema, creado_en
 from conteos_stock where ficha_id is null
 order by articulo_id, creado_en desc
),
caj(articulo_id, cuando, bultos) as (
 select c.articulo_id, (c.procesada_el at time zone
   'America/Argentina/Buenos_Aires')::date, coalesce(c.cantidad_cajones_real, 0)
 from compras c where c.estado = 'recepcionado'
 union all
 select m.articulo_id, m.fecha_operacion, m.cantidad from movimientos_stock m
 where m.anulado_el is null and m.cantidad > 0
   and m.tipo <> 'cierre_modelo_viejo'
   and (m.destino_rechazo is null or m.destino_rechazo = 'stock')
)
select a.nombre as articulo,
 (u.creado_en at time zone 'America/Argentina/Buenos_Aires')::timestamp(0) as conto,
 u.cantidad as contado, u.stock_sistema as sistema,
 coalesce(sum(k.bultos) filter (where k.cuando >= (select fecha from c0)), 0)
   as caj_desde_corte,
 coalesce(sum(k.bultos) filter (where k.cuando < (select fecha from c0)), 0)
   as caj_antes_corte,
 coalesce(sum(k.bultos) filter (where k.cuando is null), 0) as caj_sin_fecha
from ult u
join articulos a on a.id = u.articulo_id
left join caj k on k.articulo_id = u.articulo_id
group by a.nombre, u.creado_en, u.cantidad, u.stock_sistema
order by u.cantidad desc;
