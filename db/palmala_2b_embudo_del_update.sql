-- EL EMBUDO: el WHERE del UPDATE aplicado de a una condición. El paso donde
-- el número cae a cero es la condición culpable. Read-only.
-- No "arregla" nada: sirve para saber QUÉ difiere antes de tocar el UPDATE.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
r as (
    select r.id, r.articulo_id, r.texto_codigo,
           regexp_replace(translate(lower(btrim(coalesce(r.texto_codigo,''))),
                          'áéíóúüñ','aeiouun'), '\s+',' ','g') as cod
    from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id
    join cli on cli.id = p.cliente_id
    where p.anulado_el is null and r.anulado_el is null and r.ficha_id is null
),
m as (
    select r.*,
      (select count(*) from fichas_logistica f, cli
        where f.cliente_id = cli.id and f.codigo_cliente is not null
          and translate(lower(btrim(f.codigo_cliente)),'áéíóúüñ','aeiouun') = r.cod
      ) as matchean,
      (select count(*) from fichas_logistica f, cli
        where f.cliente_id = cli.id and f.codigo_cliente is not null
          and translate(lower(btrim(f.codigo_cliente)),'áéíóúüñ','aeiouun') = r.cod
          and (r.articulo_id is null or f.articulo_id = r.articulo_id)
      ) as matchean_mismo_articulo
    from r
)
select
  (select count(*) from clientes where nombre ilike '%Día%') as clientes_que_matchean,
  (select count(*) from fichas_logistica f, cli
    where f.cliente_id = cli.id and f.codigo_cliente is not null) as fichas_con_codigo,
  count(*)                                                   as p0_sin_ficha,
  count(*) filter (where cod <> '')                          as p1_con_codigo_normalizado,
  count(*) filter (where coalesce(texto_codigo,'') <> '')    as p1b_con_codigo_crudo,
  count(*) filter (where cod <> '' and matchean >= 1)        as p2_matchea_alguna,
  count(*) filter (where cod <> '' and matchean = 1)         as p3_matchea_una_sola,
  count(*) filter (where cod <> '' and matchean = 1
                     and matchean_mismo_articulo = 1)        as p4_mismo_articulo
from m;
