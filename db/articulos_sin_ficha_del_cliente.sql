-- Qué artículos aparecen en renglones SIN FICHA, y si el cliente tiene ficha
-- de ese artículo. Es la pregunta que decide si el backfill sirve: sin ficha
-- para elegir, no hay nada que recuperar y lo que falta son fichas, no código.
-- Incluye los renglones SIN IDENTIFICAR (articulo_id NULL) como su propia
-- fila: ahí no falta la ficha, falta saber qué es.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
sin_ficha as (
    select r.articulo_id, r.texto_descripcion, r.texto_codigo,
           coalesce(r.kilos_enviados, 0) as unidades,
           (r.armado_el is not null) as armado
    from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id
    join cli on cli.id = p.cliente_id
    where p.anulado_el is null and r.anulado_el is null and r.ficha_id is null
)
select coalesce(a.nombre, '(sin identificar: ' || coalesce(sf.texto_descripcion,
                                                          sf.texto_codigo, '?') || ')') as articulo,
       a.activo as articulo_activo,
       (select count(*) from fichas_logistica f, cli
         where f.articulo_id = sf.articulo_id and f.cliente_id = cli.id) as fichas_del_cliente,
       count(*) as renglones,
       count(*) filter (where sf.armado) as armados,
       round(sum(sf.unidades), 2) as unidades_entregadas,
       case
         when sf.articulo_id is null then 'FALTA IDENTIFICAR el renglon'
         when not exists (select 1 from fichas_logistica f, cli
                           where f.articulo_id = sf.articulo_id and f.cliente_id = cli.id)
              then 'FALTA LA FICHA: el backfill no puede recuperarlo'
         else 'hay ficha: el backfill deberia poder'
       end as veredicto
from sin_ficha sf
left join articulos a on a.id = sf.articulo_id
group by a.nombre, a.activo, sf.articulo_id, sf.texto_descripcion, sf.texto_codigo
order by veredicto, unidades_entregadas desc nulls last;
