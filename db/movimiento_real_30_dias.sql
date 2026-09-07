-- Cuánto movimiento REAL hay en los últimos 30 días, por fecha: cuántos
-- renglones se armaron, cuántas unidades salieron y cuánta plata es. Es la
-- misma cuenta que la incidencia de Márgenes por Artículo (kilos_enviados x
-- precio vigente A LA FECHA DEL PEDIDO), así que si acá da poco, el
-- porcentaje de esa pantalla está calculado sobre poco.
-- ORIGEN y MAIL son la señal de "es de verdad": un pedido con
-- mail_message_id vino de una casilla real; uno 'texto' se tipeó a mano y
-- puede ser tanto un pedido por teléfono como una carga de prueba.
-- Cambiar el nombre del cliente de abajo.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
vigentes as (
    select distinct on (p.fecha_operacion)
           p.id, p.fecha_operacion, p.origen,
           (p.mail_message_id is not null) as de_mail,
           p.creado_en
    from pedidos p join cli on cli.id = p.cliente_id
    where p.anulado_el is null
      and p.fecha_operacion > (now() at time zone 'America/Argentina/Buenos_Aires')::date - 30
    order by p.fecha_operacion, p.creado_en desc
)
select v.fecha_operacion, v.origen, v.de_mail,
       v.creado_en::date as pedido_cargado_el,
       count(*) filter (where r.id is not null) as renglones,
       count(*) filter (where r.armado_el is not null) as armados,
       count(*) filter (where r.kilos_enviados is not null) as con_kilaje,
       round(sum(r.kilos_enviados), 2) as unidades,
       round(sum(r.kilos_enviados * p.precio), 2) as plata
from vigentes v
left join pedidos_renglones r
       on r.pedido_id = v.id and r.anulado_el is null
left join lateral (
    select precio from precios_venta_historial pv
    where pv.ficha_id = r.ficha_id and pv.vigente_desde <= v.fecha_operacion
    order by pv.vigente_desde desc limit 1
) p on true
group by v.fecha_operacion, v.origen, v.de_mail, v.creado_en::date
order by v.fecha_operacion desc;
