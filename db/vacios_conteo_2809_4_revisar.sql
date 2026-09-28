with mov as (
  select f.proveedor_id as p, null::bigint as m, f.cantidad as c from vacios_deposito_foto f
  union all
  select co.proveedor_id, co.marca_vacio_id, coalesce(co.cantidad_cajones_real, co.cantidad_cajones)
    from compras co left join vacios_deposito_foto f on f.proveedor_id = co.proveedor_id
   where co.estado = 'recepcionado' and co.procesada_el is not null and coalesce(co.sena, 0) > 0
     and (f.creado_en is null or co.procesada_el > f.creado_en)
  union all
  select d.proveedor_id, d.marca_vacio_id, -d.cantidad
    from vacios_deposito_devoluciones d left join vacios_deposito_foto f on f.proveedor_id = d.proveedor_id
   where d.anulado_el is null and (f.creado_en is null or d.creado_en > f.creado_en)
  union all
  select proveedor_id, marca_vacio_id, cantidad from vacios_deposito_ajustes where anulado_el is null union all
  select proveedor_id, unnest(array[marca_desde_id, marca_hasta_id]), unnest(array[-cantidad, cantidad])
    from vacios_deposito_asignaciones where anulado_el is null
),
hoy as (select p, m, sum(c) as c from mov group by p, m),
nuevo as (
  select t.orden, t.pn, t.marca, t.cant, b.proveedor_id as p, b.iguales, b.parecidos,
         mv.marca_id as m, mv.nombre_actual, mv.parecidas
    from vacios_conteo_2809() t, vacios_conteo_2809_proveedor(t.pn) b,
         vacios_conteo_2809_marca(b.proveedor_id, t.marca) mv
)
select 'vacios_conteo_2809_4_revisar' as que_consulta,
       coalesce(pr.nombre, case when n.pn = 'sin proveedor' then 'Sin Proveedor (nuevo)' end,
         'NO SE ENCUENTRA ' || n.pn || ': ' || n.iguales || ' iguales, ' || n.parecidos || ' parecidos') as proveedor,
       coalesce(n.marca, mv.nombre, 'sin asignar') as marca,
       coalesce(h.c, 0) as stock_hoy,
       coalesce(n.cant, 0) as queda,
       case when n.orden is null then 'va a cero'
       when n.m is null and n.parecidas > 0 then 'ABORTA: ' || n.parecidas || ' marcas parecidas'
       when n.m is null then 'marca nueva'
       when n.nombre_actual <> n.marca then 'reusa "' || n.nombre_actual || '"'
       else 'reusa' end as que_pasa
  from nuevo n
  full join hoy h on h.p = n.p and h.m = n.m
  left join proveedores pr on pr.id = coalesce(n.p, h.p)
  left join marcas_vacio mv on mv.id = h.m
 where n.orden is not null or h.c <> 0
 order by n.orden nulls last, pr.nombre, mv.nombre nulls first;

-- VACÍOS 28/09, bloque 4: SOLO LEE. Con NO SE ENCUENTRA o ABORTA en
-- alguna fila, el bloque 5 no escribe nada.
