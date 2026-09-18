with mov as (
  select c.articulo_id, 'ingreso' as que, c.fecha_operacion as fecha_del_movimiento,
         (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date as fecha_de_carga,
         c.cantidad_cajones_real as bultos, c.id as id_origen
    from compras c
   where c.estado = 'recepcionado' and c.procesada_el is not null
     and c.fecha_operacion between date '2026-09-14' and date '2026-09-20'
  union all
  select r.articulo_id, 'armado',
         (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date,
         (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date,
         coalesce(r.cantidad_armada, r.cantidad), r.id
    from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id and p.anulado_el is null
   where r.armado_el is not null and r.anulado_el is null and r.articulo_id is not null
     and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date
         between date '2026-09-14' and date '2026-09-20'
)
select a.nombre                                        as ARTICULO,
       mov.que, mov.fecha_del_movimiento, mov.fecha_de_carga,
       mov.bultos, mov.id_origen,
       case when mov.que = 'ingreso' and mov.fecha_de_carga > mov.fecha_del_movimiento
            then 'CARGADO DESPUES DE SU FECHA' else '' end as OJO,
       (select count(*) from compras where estado = 'recepcionado')  as COMPRAS_POBLACION,
       (select max(fecha_operacion) from pedidos where anulado_el is null)
                                                       as TESTIGO_ultimo_pedido
  from mov join articulos a on a.id = mov.articulo_id
 where a.nombre ilike '%rand%'
 order by mov.fecha_del_movimiento, mov.que;
