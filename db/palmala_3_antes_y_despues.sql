-- BLOQUE 3 de 3 — EL ANTES Y DESPUÉS. Read-only: antes del bloque 2 para
-- saber qué se va a mover, después para confirmar que se movió eso.
-- Solo mueve plata lo ARMADO: kilos_enviados se escribe en el mismo UPDATE
-- que el tilde, así que un renglón nunca tildado no factura, tenga ficha o no.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
fi as (
    select f.id, f.articulo_id,
           translate(lower(btrim(f.codigo_cliente)),'áéíóúüñ','aeiouun') as cod
    from fichas_logistica f join cli on cli.id = f.cliente_id
    where f.codigo_cliente is not null
),
r as (
    select p.fecha_operacion, r.kilos_enviados, r.ficha_id as ficha_hoy,
           coalesce(r.ficha_id, (
               select f.id from fi f
               where f.cod = regexp_replace(translate(lower(btrim(coalesce(r.texto_codigo,''))),
                                            'áéíóúüñ','aeiouun'), '\s+',' ','g')
                 and coalesce(r.texto_codigo,'') <> ''
                 and (r.articulo_id is null or r.articulo_id = f.articulo_id)
                 and (select count(*) from fi f2 where f2.cod = f.cod) = 1
           )) as ficha_despues
    from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id
    join cli on cli.id = p.cliente_id
    where p.anulado_el is null and r.anulado_el is null
      and p.fecha_operacion > (now() at time zone 'America/Argentina/Buenos_Aires')::date - 30
)
select
  count(distinct r.fecha_operacion) filter
      (where r.ficha_hoy is not null and r.kilos_enviados is not null) as dias_antes,
  count(distinct r.fecha_operacion) filter
      (where r.ficha_despues is not null and r.kilos_enviados is not null) as dias_despues,
  round(sum(r.kilos_enviados * ph.precio) filter (where r.ficha_hoy is not null), 2) as plata_antes,
  round(sum(r.kilos_enviados * pd.precio) filter (where r.ficha_despues is not null), 2) as plata_despues,
  count(*) filter (where r.ficha_hoy is null and r.ficha_despues is not null
                     and r.kilos_enviados is not null) as recupera_armados
from r
left join lateral (select precio from precios_venta_historial v
    where v.ficha_id = r.ficha_hoy and v.vigente_desde <= r.fecha_operacion
    order by v.vigente_desde desc limit 1) ph on true
left join lateral (select precio from precios_venta_historial v
    where v.ficha_id = r.ficha_despues and v.vigente_desde <= r.fecha_operacion
    order by v.vigente_desde desc limit 1) pd on true;
