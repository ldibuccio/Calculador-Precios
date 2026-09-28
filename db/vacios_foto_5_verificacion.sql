with b as (
  select distinct on (proveedor_id) proveedor_id, cantidad, fecha
    from conteos_vacios_deposito where fecha <= date '2026-09-25'
   order by proveedor_id, fecha, id
), x as (
  select f.cantidad as foto, coalesce(b.cantidad
    + (select coalesce(sum(coalesce(c.cantidad_cajones_real, c.cantidad_cajones)), 0)
         from compras c where c.proveedor_id = f.proveedor_id and c.estado = 'recepcionado'
          and coalesce(c.sena, 0) > 0 and c.procesada_el <= f.creado_en
          and (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date >= b.fecha)
    - (select coalesce(sum(d.cantidad), 0) from vacios_deposito_devoluciones d
        where d.proveedor_id = f.proveedor_id and d.anulado_el is null
          and d.creado_en <= f.creado_en
          and (d.creado_en at time zone 'America/Argentina/Buenos_Aires')::date >= b.fecha), 0) as regla
    from vacios_deposito_foto f left join b on b.proveedor_id = f.proveedor_id
)
select 'vacios_foto_4_corregir_con_sena' as que_migracion,
  count(*) filter (where foto <> regla) as fuera_de_la_regla,
  count(*) as fotos,
  sum(foto) as foto_total,
  count(*) filter (where foto < 0) as negativas,
  (select max(procesada_el) from compras where estado = 'recepcionado') as ultima_recepcion
from x;

-- Se corre DESPUÉS del bloque, aparte. fuera_de_la_regla tiene que dar 0.
