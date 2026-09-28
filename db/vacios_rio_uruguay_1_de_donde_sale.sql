with buscado as (select '%rio uruguay%' as t),
prov as (
  select p.id, p.nombre, f.cantidad as foto, f.creado_en as foto_el
    from proveedores p
    left join vacios_deposito_foto f on f.proveedor_id = p.id, buscado b
   where translate(lower(p.nombre), 'áéíóú', 'aeiou') like b.t
      or exists (select 1 from compras c where c.proveedor_id = p.id
                   and translate(lower(c.marca), 'áéíóú', 'aeiou') like b.t)
),
rec as (
  select c.proveedor_id,
         coalesce(c.cantidad_cajones_real, c.cantidad_cajones) as cj,
         coalesce(c.sena, 0) > 0 as sena, c.retiro_origen as via
    from compras c join prov p on p.id = c.proveedor_id
   where c.estado = 'recepcionado' and c.procesada_el is not null
     and (p.foto_el is null or c.procesada_el > p.foto_el)
)
select 'vacios_rio_uruguay_1' as que_consulta, p.nombre as proveedor,
  p.foto, p.foto_el,
  coalesce(sum(r.cj), 0) as recibidos_todos,
  coalesce(sum(r.cj) filter (where r.sena), 0) as SUMAN_con_sena,
  coalesce(sum(r.cj) filter (where not r.sena), 0) as NO_SUMAN_sin_sena,
  coalesce(sum(r.cj) filter (where r.via = 'logistica'), 0) as via_logistica,
  coalesce(sum(r.cj) filter (where r.via = 'deposito'), 0) as via_deposito,
  coalesce(sum(r.cj) filter (where r.via = 'ingreso_directo'), 0) as via_ingreso_directo,
  coalesce(sum(r.cj) filter (where r.via not in ('logistica', 'deposito', 'ingreso_directo')
                                or r.via is null), 0) as via_otra,
  coalesce(sum(r.cj) filter (where r.via = 'ingreso_directo' and r.sena), 0)
    as ingreso_directo_con_sena,
  (select coalesce(sum(d.cantidad), 0) from vacios_deposito_devoluciones d
    where d.proveedor_id = p.id and d.anulado_el is null
      and (p.foto_el is null or d.creado_en > p.foto_el)) as devueltos,
  (select coalesce(sum(a.cantidad), 0) from vacios_deposito_ajustes a
    where a.proveedor_id = p.id and a.anulado_el is null) as ajustes,
  count(r.*) as compras
from prov p left join rec r on r.proveedor_id = p.id
group by p.id, p.nombre, p.foto, p.foto_el;

-- DE DÓNDE SALE EL STOCK DE VACÍOS DE UN PROVEEDOR (28/09). Solo lee.
-- El stock que muestra Vacíos es foto + SUMAN_con_sena − devueltos
-- ± ajustes (las asignaciones mueven entre marcas, no cambian el total).
-- Lo recibido SIN seña no suma: decisión del 25/09.
-- Busca por nombre del proveedor o por la marca escrita en sus compras.
