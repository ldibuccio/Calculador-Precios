with vigentes as (
  select distinct on (cliente_id, fecha_operacion) id
    from pedidos where anulado_el is null
   order by cliente_id, fecha_operacion, creado_en desc
),
armados as (
  select r.articulo_id,
         (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date as fecha,
         sum(coalesce(r.cantidad_armada, r.cantidad)) as bultos
    from pedidos_renglones r join vigentes v on v.id = r.pedido_id
   where r.armado_el is not null and r.anulado_el is null and r.articulo_id is not null
   group by 1, 2
),
-- LAS SEIS PATAS de _SQL_SUMAS_STOCK (app/db.py), con SIGNO, para poder
-- acumularlas por fecha. Si alguna cambia alla, esta consulta miente.
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
)
select count(*) filter (where saldo < 0)                     as DIAS_ARTICULO_EN_ROJO,
       count(distinct articulo_id) filter (where saldo < 0)  as ARTICULOS_DISTINTOS,
       coalesce(-sum(saldo) filter (where saldo < 0), 0)     as BULTOS_DESCUBIERTOS,
       max(fecha) filter (where saldo < 0)                   as EL_MAS_RECIENTE,
       count(*)                                              as DIAS_ARTICULO_POBLACION,
       (select max(fecha_operacion) from pedidos where anulado_el is null)
                                                             as TESTIGO_ultimo_pedido
  from dias;
