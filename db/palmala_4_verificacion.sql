-- VERIFICACIÓN del backfill: no alcanza con que sea CONSISTENTE, tiene que ser
-- LA ficha que la regla de matcheo habría elegido. Los tres primeros números
-- tienen que dar CERO; el cuarto es informativo.
--   cruzados_articulo: la ficha es de OTRO artículo que el renglón. Imposible
--     por construcción en este backfill (setea los dos juntos), así que si
--     aparece algo es de otra escritura y hay que mirarlo.
--   cruzados_cliente: la ficha es de otro CLIENTE. Sería lo más grave.
--   ficha_sin_articulo: lo prohíbe el CHECK, se chequea igual.
--   codigo_no_coincide: la ficha asignada NO tiene el código del renglón. NO
--     es un error: son los asignados por NOMBRE o por el backfill viejo del
--     26/08, que emparejaba por (cliente, artículo) sin mirar el código.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
x as (
    select r.id, r.articulo_id, r.ficha_id, r.texto_codigo,
           f.articulo_id as ficha_articulo, f.cliente_id as ficha_cliente,
           translate(lower(btrim(f.codigo_cliente)),'áéíóúüñ','aeiouun') as ficha_cod,
           regexp_replace(translate(lower(btrim(coalesce(r.texto_codigo,''))),
                          'áéíóúüñ','aeiouun'), '\s+',' ','g') as reng_cod
    from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id
    join cli on cli.id = p.cliente_id
    left join fichas_logistica f on f.id = r.ficha_id
    where p.anulado_el is null and r.anulado_el is null
)
select count(*) filter (where ficha_id is not null)          as con_ficha,
       count(*) filter (where ficha_id is null)              as todavia_sin_ficha,
       count(*) filter (where ficha_id is not null
                          and ficha_articulo <> articulo_id) as cruzados_articulo,
       count(*) filter (where ficha_id is not null
                          and ficha_cliente <> (select id from cli)) as cruzados_cliente,
       count(*) filter (where ficha_id is not null
                          and articulo_id is null)           as ficha_sin_articulo,
       count(*) filter (where ficha_id is not null and reng_cod <> ''
                          and (ficha_cod is null or ficha_cod <> reng_cod)) as codigo_no_coincide
from x;
