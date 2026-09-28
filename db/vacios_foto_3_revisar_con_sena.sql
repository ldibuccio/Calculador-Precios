with b as (
  select distinct on (proveedor_id) proveedor_id, cantidad, fecha
    from conteos_vacios_deposito where fecha <= date '2026-09-25'
   order by proveedor_id, fecha, id
),
x as (
  select f.proveedor_id, f.cantidad as foto_actual, f.creado_en, b.fecha as conteo_el,
         b.cantidad as contado,
    (select coalesce(sum(coalesce(c.cantidad_cajones_real, c.cantidad_cajones))
            filter (where coalesce(c.sena, 0) > 0), 0)
       from compras c where c.proveedor_id = f.proveedor_id and c.estado = 'recepcionado'
        and c.procesada_el <= f.creado_en
        and (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date >= b.fecha) as con_sena,
    (select coalesce(sum(coalesce(c.cantidad_cajones_real, c.cantidad_cajones)), 0)
       from compras c where c.proveedor_id = f.proveedor_id and c.estado = 'recepcionado'
        and c.procesada_el <= f.creado_en
        and (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date >= b.fecha) as todas,
    (select coalesce(sum(d.cantidad), 0) from vacios_deposito_devoluciones d
      where d.proveedor_id = f.proveedor_id and d.anulado_el is null
        and d.creado_en <= f.creado_en
        and (d.creado_en at time zone 'America/Argentina/Buenos_Aires')::date >= b.fecha) as devueltos
    from vacios_deposito_foto f left join b on b.proveedor_id = f.proveedor_id
)
select 'vacios_foto_3_revisar' as que_consulta, p.nombre as proveedor, x.conteo_el, x.contado,
  x.con_sena, x.todas - x.con_sena as sin_sena, x.devueltos,
  x.foto_actual,
  coalesce(x.contado + x.todas - x.devueltos, 0) as control_regla_vieja,
  coalesce(x.contado + x.con_sena - x.devueltos, 0) as foto_nueva,
  x.foto_actual - coalesce(x.contado + x.con_sena - x.devueltos, 0) as baja
from x join proveedores p on p.id = x.proveedor_id
order by baja desc, p.nombre;

-- SOLO LEE. La foto de vacíos del 25/09 recalculada con la regla de la
-- seña: conteo + cajones CON SEÑA − devueltos, desde el primer conteo
-- hasta el instante de la foto. control_regla_vieja rehace la foto con
-- TODOS los cajones: tiene que dar igual a foto_actual en cada fila, o la
-- reconstrucción no es la misma cuenta. Sin conteo, la foto era 0 y sigue.
