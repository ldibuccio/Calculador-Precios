with vigentes as (
  select distinct on (cliente_id, fecha_operacion) id
    from pedidos where anulado_el is null
   order by cliente_id, fecha_operacion, creado_en desc
),
mov as (
  select c.articulo_id, 'ingreso' as que,
         coalesce((c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date,
                  c.fecha_operacion) as fecha,
         c.fecha_operacion as fecha_de_compra,
         c.cantidad_cajones_real as bultos, c.id as id_origen
    from compras c where c.estado = 'recepcionado'
  union all
  select m.articulo_id, 'mov: ' || m.tipo, m.fecha_operacion, m.fecha_operacion,
         m.cantidad, m.id
    from movimientos_stock m
   where m.anulado_el is null
     and (m.tipo <> 'reingreso_rechazo'
          or m.destino_rechazo is null or m.destino_rechazo = 'stock')
  union all
  select rp.articulo_id, 'guia R', rp.fecha_operacion, rp.fecha_operacion,
         rp.bultos_primera - rp.bultos_tomados, rp.id
    from reprocesos rp where rp.anulado_el is null
  union all
  select r.articulo_id, 'armado',
         (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date,
         (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date,
         -coalesce(r.cantidad_armada, r.cantidad), r.id
    from pedidos_renglones r join vigentes v on v.id = r.pedido_id
   where r.armado_el is not null and r.anulado_el is null and r.articulo_id is not null
)
select a.nombre as ARTICULO, mov.que, mov.fecha, mov.bultos,
       sum(mov.bultos) over (partition by mov.articulo_id order by mov.fecha
                             range between unbounded preceding and current row)
                                                       as SALDO_A_ESA_FECHA,
       mov.id_origen,
       case when mov.que = 'ingreso' and mov.fecha > mov.fecha_de_compra
            then 'CARGADO DESPUES DE SU FECHA' else '' end as OJO,
       (select max(fecha_operacion) from pedidos where anulado_el is null)
                                                       as TESTIGO_ultimo_pedido
  from mov join articulos a on a.id = mov.articulo_id
 where a.nombre ilike '%rand%'  -- <<< cambiar para otro articulo
 order by mov.fecha, mov.que;

-- LAS SEIS PATAS de _SQL_SUMAS_STOCK (app/db.py), con signo: con menos patas
-- dice "no entro nada" en un articulo que se mueve por guia R (corolario 85).
-- VIGENTES: un pedido RECARGADO no se anula; sin eso el armado sale dos veces.
-- RANGE y no ROWS: el saldo es el de FIN DEL DIA, como la regla real.
