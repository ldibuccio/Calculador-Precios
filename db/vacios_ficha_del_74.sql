-- ############################################################################
-- TODO LO QUE EL SISTEMA GUARDA DE UNA RECEPCIÓN DE VACÍOS. Solo lectura.
-- Cambiar el 74 de la primera línea por el id que se quiera mirar.
--
-- LO QUE NO VA A APARECER, y no es que falte la consulta: el sistema NO guarda
-- QUIÉN cargó ni QUIÉN anuló. No hay login, `vacios_recibidos` no tiene
-- columna de usuario, y la única bitácora del proyecto es la de fichas. El
-- "quién" hay que preguntarlo en el puesto.
--
-- El VALE tampoco tiene número, cobro ni vencimiento: `sena_vale_el` es todo
-- lo que existe de él acá adentro. El papel está afuera del sistema.
-- ############################################################################
with r as (
  select v.id, v.cantidad, v.proveedor_id, v.tipo_envase_id,
         c.nombre cliente, p.nombre proveedor, t.nombre tipo, valor.monto,
         to_char(v.creado_en at time zone 'America/Argentina/Buenos_Aires',
                 'DD/MM/YYYY HH24:MI') recibido,
         case when v.sena_pagada_el is not null then 'PAGADA '
              when v.sena_vale_el is not null then 'VALE '
              when v.sena_anulada_el is not null then 'ANULADA ' end
         || to_char(coalesce(v.sena_pagada_el, v.sena_vale_el, v.sena_anulada_el)
                    at time zone 'America/Argentina/Buenos_Aires', 'DD/MM/YYYY HH24:MI') cerrada,
         to_char(v.anulado_el at time zone 'America/Argentina/Buenos_Aires',
                 'DD/MM/YYYY HH24:MI') anulada
  from vacios_recibidos v
  join clientes_puesto c on c.id = v.cliente_puesto_id
  join proveedores_puesto p on p.id = v.proveedor_id
  join tipos_envase_puesto t on t.id = v.tipo_envase_id
  left join lateral (
    select h.monto from senas_valor_historial h
    where h.tipo_envase_id = v.tipo_envase_id and h.vigente_desde <= v.creado_en::date
    order by h.vigente_desde desc, h.creado_en desc limit 1) valor on true
  where v.id = 74
)
select orden, dato, valor from (
  select 1 orden, 'cliente que lo trajo' dato, r.cliente valor from r
  union all select 2, 'proveedor · tipo', r.proveedor || ' · ' || r.tipo from r
  union all select 3, 'cantidad', r.cantidad || ' cajones' from r
  union all select 4, '1. RECIBIDO', r.recibido from r
  union all select 5, '2. SEÑA CERRADA', coalesce(r.cerrada, 'sin cerrar') from r
  union all select 6, '3. RECEPCIÓN ANULADA', coalesce(r.anulada, 'no') from r
  union all select 7, 'seña por cajón / total',
    coalesce(r.monto::text, 'sin valor') || ' / ' || coalesce((r.monto*r.cantidad)::text, '?') from r
  union all select 8, 'quién cargó / quién anuló', 'EL SISTEMA NO LO GUARDA' from r
  union all select 9, 'el vale en otro lado', 'NO EXISTE: sena_vale_el es todo' from r
) f order by orden;

-- ############################################################################
-- SEGUNDA CONSULTA, aparte porque el editor solo muestra la última: EL STOCK
-- de ese proveedor + tipo de envase hoy, y cuánto sería si la recepción no
-- estuviera anulada. La diferencia entre las dos columnas es lo que está en
-- juego en el piso.
-- ############################################################################
select p.nombre proveedor, t.nombre tipo, v.cantidad anulados,
       coalesce((select sum(x.cantidad) from vacios_recibidos x
                 where x.anulado_el is null and x.proveedor_id = v.proveedor_id
                   and x.tipo_envase_id = v.tipo_envase_id), 0)
     - coalesce((select sum(x.cantidad) from vacios_devueltos x
                 where x.anulado_el is null and x.proveedor_id = v.proveedor_id
                   and x.tipo_envase_id = v.tipo_envase_id), 0)
     + coalesce((select sum(x.cantidad) from ajustes_vacios x
                 where x.anulado_el is null and x.proveedor_id = v.proveedor_id
                   and x.tipo_envase_id = v.tipo_envase_id), 0) stock_hoy
from vacios_recibidos v
join proveedores_puesto p on p.id = v.proveedor_id
join tipos_envase_puesto t on t.id = v.tipo_envase_id
where v.id = 74;
