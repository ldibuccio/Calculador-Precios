with c0 as (select fecha as corte from corte_modelo where id = 1),
vigentes as (
  select distinct on (cliente_id, fecha_operacion) id from pedidos
   where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc
),
armados as (
  select r.articulo_id,
         (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date as fecha,
         sum(coalesce(r.cantidad_armada, r.cantidad)) as bultos
    from pedidos_renglones r join vigentes v on v.id = r.pedido_id
   where r.armado_el is not null and r.anulado_el is null and r.articulo_id is not null
   group by 1, 2
  having sum(coalesce(r.cantidad_armada, r.cantidad)) > 0
),
eventos as (
  select c.articulo_id,
         coalesce((c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date,
                  c.fecha_operacion) as fecha,
         c.cantidad_cajones_real as bultos
    from compras c where c.estado = 'recepcionado'
  union all
  select m.articulo_id, m.fecha_operacion, m.cantidad
    from movimientos_stock m
   where m.anulado_el is null
     and (m.tipo <> 'reingreso_rechazo'
          or m.destino_rechazo is null or m.destino_rechazo = 'stock')
  union all
  select rp.articulo_id, rp.fecha_operacion, rp.bultos_primera - rp.bultos_tomados
    from reprocesos rp where rp.anulado_el is null
  union all
  select a.articulo_id, a.fecha, -a.bultos from armados a
),
dias as (
  select a.articulo_id, a.fecha,
         (select coalesce(sum(e.bultos), 0) from eventos e
           where e.articulo_id = a.articulo_id and e.fecha <= a.fecha) as saldo
    from armados a
),
recien as (
  select articulo_id, fecha, falta,
         greatest(falta - lag(falta, 1, 0)
                  over (partition by articulo_id order by fecha), 0) as nuevo
    from (select articulo_id, fecha, greatest(-saldo,0) as falta from dias
          where fecha > (select corte from c0)) f
)
select (select corte from c0) as CORTE,
       count(*) filter (where falta > 0) as DESDE_EL_CORTE,
       (select count(*) from dias where saldo < 0) as TODA_LA_HISTORIA,
       count(distinct articulo_id) filter (where falta > 0) as ARTS,
       coalesce(sum(nuevo), 0) as SIN_COBERTURA,
       count(*) as POBLACION,
       max(fecha) filter (where falta > 0) as ULTIMO,
       (select max(fecha_operacion) from pedidos where anulado_el is null)
 as TESTIGO_ult_pedido
  from recien;

-- `> corte` y NO `>=` (corolario 12). TODA_LA_HISTORIA es el canario: tiene
-- que dar el mismo 45 de rojo_a_su_fecha_1.
