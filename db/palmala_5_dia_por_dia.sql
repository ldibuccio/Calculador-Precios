-- DÍA POR DÍA: qué días cuentan como "con entregas armadas", cuáles no, y por
-- qué. Una fila por fecha con pedido vigente en la ventana, ordenada de nueva
-- a vieja. La columna CUENTA_COMO_DIA es la condición exacta del contador:
-- al menos un renglón con ficha Y con kilos_enviados.
-- Muestra también el BORDE de la ventana: si un día viejo se cayó afuera
-- mientras entraba uno nuevo, el total puede quedar igual y parecer que no
-- pasó nada.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
borde as (select (now() at time zone 'America/Argentina/Buenos_Aires')::date - 30 as desde),
vigentes as (
    select distinct on (p.fecha_operacion) p.id, p.fecha_operacion, p.creado_en
    from pedidos p join cli on cli.id = p.cliente_id, borde
    where p.anulado_el is null and p.fecha_operacion > borde.desde
    order by p.fecha_operacion, p.creado_en desc
)
select v.fecha_operacion,
       count(r.id) as renglones,
       count(r.id) filter (where r.armado_el is not null) as armados,
       count(r.id) filter (where r.kilos_enviados is not null) as con_kilos,
       count(r.id) filter (where r.ficha_id is not null
                             and r.kilos_enviados is not null) as con_ficha_y_kilos,
       round(sum(r.kilos_enviados * pr.precio), 2) as plata,
       (count(r.id) filter (where r.ficha_id is not null
                              and r.kilos_enviados is not null) > 0) as cuenta_como_dia
from vigentes v
left join pedidos_renglones r on r.pedido_id = v.id and r.anulado_el is null
left join lateral (
    select precio from precios_venta_historial pv
    where pv.ficha_id = r.ficha_id and pv.vigente_desde <= v.fecha_operacion
    order by pv.vigente_desde desc limit 1) pr on true
group by v.fecha_operacion
order by v.fecha_operacion desc;
