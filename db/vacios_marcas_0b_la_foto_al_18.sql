with k as (select date '2026-09-18' as d),
base as (
  select distinct on (proveedor_id) proveedor_id, cantidad, fecha
    from conteos_vacios_deposito order by proveedor_id, fecha, id
), rec as (
  select c.proveedor_id,
         coalesce(c.cantidad_cajones_real, c.cantidad_cajones) as cajones,
         (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date as dia,
         coalesce(c.sena, 0) > 0 as con_sena
    from compras c
   where c.estado = 'recepcionado' and c.procesada_el is not null
), dev as (
  select proveedor_id, cantidad,
         (creado_en at time zone 'America/Argentina/Buenos_Aires')::date as dia
    from vacios_deposito_devoluciones where anulado_el is null
), foto as (
  select b.cantidad
         + coalesce((select sum(r.cajones) from rec r, k where r.proveedor_id = b.proveedor_id
                      and r.dia >= b.fecha and r.dia < k.d), 0)
         - coalesce((select sum(r.cajones) from rec r, k where r.proveedor_id = b.proveedor_id
                      and r.dia >= k.d and r.dia < b.fecha), 0)
         + coalesce((select sum(v.cantidad) from dev v, k where v.proveedor_id = b.proveedor_id
                      and v.dia >= k.d and v.dia < b.fecha), 0) as cajones
    from base b
)
select
  (select d from k) as corte,
  (select count(*) from base) as proveedores_con_conteo,
  (select count(*) from base, k where fecha < k.d) as conteos_ANTES_del_corte,
  (select count(*) from base, k where fecha >= k.d) as conteos_DESDE_el_corte,
  (select max(fecha) from base) as conteo_mas_nuevo,
  (select count(*) from foto where cajones < 0) as fotos_NEGATIVAS_0,
  (select coalesce(sum(cajones), 0) from foto)::int as FOTO_total,
  ((select coalesce(sum(cajones), 0) from foto)
   + (select coalesce(sum(cajones), 0) from rec, k where con_sena and dia >= k.d)
   - (select coalesce(sum(cantidad), 0) from dev, k where dia >= k.d))::int as STOCK_NUEVO,
  (select coalesce(sum(cajones), 0) from rec, k where not con_sena and dia >= k.d)::int as cajones_SIN_sena_desde,
  (select count(*) from dev, k where dia < k.d) as devol_ANTES_0,
  (select max(dia) from rec) as ultima_recepcion;

-- SOLO LECTURA, en las DOS bases. FOTO = lo que el sistema dice que había al
-- cierre del 17/09, leído desde cada conteo. STOCK_NUEVO = foto + lo recibido
-- con seña desde el 18 − lo devuelto. Los dos que dicen 0 tienen que dar 0.
