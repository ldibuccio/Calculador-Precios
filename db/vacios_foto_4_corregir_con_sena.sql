do $$
declare
  raras int;
  n int;
begin
  with b as (
    select distinct on (proveedor_id) proveedor_id, cantidad, fecha
      from conteos_vacios_deposito where fecha <= date '2026-09-25'
     order by proveedor_id, fecha, id
  ), x as (
    select f.proveedor_id, f.cantidad as actual, b.cantidad as contado,
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
  ), u as (
    update vacios_deposito_foto f
       set cantidad = coalesce(x.contado + x.con_sena - x.devueltos, 0)
      from x
     where x.proveedor_id = f.proveedor_id
       and f.cantidad <> coalesce(x.contado + x.con_sena - x.devueltos, 0)
    returning 1
  )
  select (select count(*) from u),
         (select count(*) from x
           where actual <> coalesce(contado + todas - devueltos, 0)
             and actual <> coalesce(contado + con_sena - devueltos, 0))
    into n, raras;
  if raras > 0 then
    raise exception '% fotos no salen ni de la regla vieja ni de la nueva: no se escribe nada', raras;
  end if;
  raise notice 'fotos corregidas %', n;
end $$;

-- LA FOTO DEL 25/09 CON LA REGLA DE LA SEÑA (28/09): conteo + cajones
-- CON SEÑA − devueltos, hasta el instante de la foto. Aborta si una foto
-- no sale de ninguna regla. Repetible. Verificación APARTE: vacios_foto_5.
