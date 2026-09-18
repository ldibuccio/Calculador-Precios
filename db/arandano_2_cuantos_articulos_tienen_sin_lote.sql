with vigentes as (
  select distinct on (cliente_id, fecha_operacion) id
    from pedidos where anulado_el is null
   order by cliente_id, fecha_operacion, creado_en desc
),
entradas as (
  select c.articulo_id, c.fecha_operacion as fecha, sum(c.cantidad_cajones_real) as bultos
    from compras c where c.estado = 'recepcionado' and c.procesada_el is not null
   group by 1, 2
),
salidas as (
  select r.articulo_id,
         (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date as fecha,
         sum(coalesce(r.cantidad_armada, r.cantidad)) as bultos
    from pedidos_renglones r join vigentes v on v.id = r.pedido_id
   where r.armado_el is not null and r.anulado_el is null and r.articulo_id is not null
   group by 1, 2
),
-- Por DIA: cuanto se habia acumulado hasta ese dia contra lo que salio hasta ese dia.
-- Es un TECHO del sin_lote real: el FIFO reparte por lote y esto suma por articulo.
dias as (
  select s.articulo_id, s.fecha,
         coalesce((select sum(e.bultos) from entradas e
                    where e.articulo_id = s.articulo_id and e.fecha <= s.fecha), 0) as entro,
         (select sum(s2.bultos) from salidas s2
           where s2.articulo_id = s.articulo_id and s2.fecha <= s.fecha) as salio
    from salidas s
)
select count(*) filter (where salio > entro)                    as DIAS_ARTICULO_EN_ROJO,
       count(distinct articulo_id) filter (where salio > entro) as ARTICULOS_DISTINTOS,
       coalesce(sum(salio - entro) filter (where salio > entro), 0) as BULTOS_DESCUBIERTOS,
       max(fecha) filter (where salio > entro)                  as EL_MAS_RECIENTE,
       count(*)                                                 as DIAS_ARTICULO_POBLACION,
       (select max(fecha_operacion) from pedidos where anulado_el is null)
                                                                as TESTIGO_ultimo_pedido
  from dias;
