with vigentes as (
    select distinct on (fecha_operacion) id, fecha_operacion
    from pedidos
    where cliente_id = 1 and anulado_el is null
      and fecha_operacion > (now() at time zone 'America/Argentina/Buenos_Aires')::date - 30
    order by fecha_operacion, creado_en desc
),
renglones as (
    select v.fecha_operacion, r.id, r.ficha_id, r.articulo_id, r.cantidad,
           r.kilos_enviados, r.anulado_el,
           (select p.precio from precios_venta_historial p
             where p.ficha_id = r.ficha_id and p.vigente_desde <= v.fecha_operacion
             order by p.vigente_desde desc limit 1) as precio,
           exists (select 1 from compras c
                    where c.articulo_id = r.articulo_id
                      and c.estado is distinct from 'rechazado'
                      and c.estado is distinct from 'no_ingresado'
                      and c.fecha_operacion >= (now() at time zone 'America/Argentina/Buenos_Aires')::date - 15) as tiene_fila
    from vigentes v join pedidos_renglones r on r.pedido_id = v.id
),
clasificado as (
    select case
        when anulado_el is not null            then '0 anulado (no cuenta)'
        when ficha_id is null                  then '1 sin identificar'
        when kilos_enviados is null            then '2 sin kilaje (sin armar)'
        when precio is null                    then '3 sin precio vigente'
        when not tiene_fila                    then '4 sin compra en 15 dias (no tiene fila)'
        else                                        '5 atribuible'
      end as balde,
      cantidad, kilos_enviados, precio
    from renglones
)
select balde,
       count(*) as renglones,
       sum(cantidad) as bultos,
       sum(kilos_enviados) as unidades,
       round(sum(kilos_enviados * precio), 2) as plata
from clasificado
group by balde
order by balde;
