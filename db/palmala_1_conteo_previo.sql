-- BLOQUE 1 de 3 — EL CONTEO PREVIO. Read-only: no escribe nada.
-- Devuelve el número que hay que pasarle al bloque 2. Si "ambiguos" o
-- "cruzados" no dan CERO, NO se corre el bloque 2: hay que mirar esos casos
-- primero, porque el backfill los va a saltear en silencio.
-- El normalizado imita normalizar_texto (core/matcheo_comanda.py) en SQL puro.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
sf as (
    select r.id, r.articulo_id,
           regexp_replace(translate(lower(btrim(coalesce(r.texto_codigo,''))),
                          'áéíóúüñ','aeiouun'), '\s+',' ','g') as cod
    from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id
    join cli on cli.id = p.cliente_id
    where p.anulado_el is null and r.anulado_el is null and r.ficha_id is null
),
fi as (
    select f.id, f.articulo_id,
           translate(lower(btrim(f.codigo_cliente)),'áéíóúüñ','aeiouun') as cod
    from fichas_logistica f join cli on cli.id = f.cliente_id
    where f.codigo_cliente is not null
)
select
  count(*) filter (where sf.cod <> '') as con_codigo,
  count(*) filter (where sf.cod <> ''
        and (select count(*) from fi where fi.cod = sf.cod) = 1) as recuperables,
  count(*) filter (where sf.cod <> ''
        and (select count(*) from fi where fi.cod = sf.cod) > 1) as ambiguos,
  count(*) filter (where sf.cod <> '' and sf.articulo_id is not null
        and exists (select 1 from fi where fi.cod = sf.cod
                      and fi.articulo_id <> sf.articulo_id)) as cruzados,
  count(*) filter (where sf.cod = '') as sin_codigo,
  count(*) as total_sin_ficha
from sf;
