with base as (
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
  select proveedor_id, cantidad, creado_en::date as dia
    from vacios_deposito_devoluciones where anulado_el is null
)
select
  (select count(*) from base) as proveedores_con_arranque,
  (select coalesce(sum(b.cantidad), 0)
        + coalesce((select sum(r.cajones) from rec r join base b2 on b2.proveedor_id = r.proveedor_id
                     where r.dia >= b2.fecha), 0)
        - coalesce((select sum(d.cantidad) from dev d join base b3 on b3.proveedor_id = d.proveedor_id
                     where d.dia >= b3.fecha), 0)
     from base b)::int as stock_HOY,
  ((select coalesce(sum(cajones), 0) from rec where con_sena)
     - (select coalesce(sum(cantidad), 0) from dev))::int as stock_SIN_ARRANQUE_con_sena,
  (select count(*) from rec where con_sena) as recepciones_con_sena,
  (select count(*) from rec where not con_sena) as recepciones_SIN_sena,
  (select coalesce(sum(cajones), 0) from rec where not con_sena)::int as cajones_sin_sena,
  (select count(*) from dev) as devoluciones,
  (select min(dia) from rec where con_sena) as primera_con_sena,
  (select max(dia) from rec) as ultima_recepcion;

-- SOLO LECTURA. Se corre antes de la migración, en las DOS bases.
-- Muestra en UNA fila cómo cambia el número de vacíos del depósito con la
-- regla nueva del dueño (25/09): sin arranque, y contando SOLO lo que vino
-- con seña. `stock_HOY` es la cuenta de hoy (arranque + recepciones desde
-- ahí − devoluciones desde ahí); `stock_SIN_ARRANQUE_con_sena` es la nueva.
-- `recepciones_SIN_sena` son las que hoy suman y con la regla nueva no.
