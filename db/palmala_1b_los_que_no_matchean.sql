-- Los renglones sin ficha cuyo CÓDIGO no matchea ninguna ficha del cliente:
-- los que el backfill NO recupera. Al lado, los códigos que sí tiene cargados
-- ese artículo, para comparar a ojo. MATCHEA_POR_NOMBRE es el SEGUNDO camino
-- del matcheo real (_armar_renglones_pedido_desde_bloque): si da true, un
-- backfill por nombre lo recuperaría — otra decisión, no la de éste.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
n as (select f.id, f.articulo_id,
             translate(lower(btrim(f.codigo_cliente)),'áéíóúüñ','aeiouun') as cod,
             regexp_replace(translate(lower(btrim(f.nombre_cliente)),
                            'áéíóúüñ','aeiouun'), '\s+',' ','g') as nom,
             f.codigo_cliente
      from fichas_logistica f join cli on cli.id = f.cliente_id)
select p.fecha_operacion, r.sucursal,
       coalesce(a.nombre, '(sin identificar)') as articulo,
       r.texto_codigo as codigo_del_pedido,
       r.texto_descripcion as texto_del_pedido,
       (select string_agg(coalesce(n.codigo_cliente,'(sin codigo)'), ' | ' order by n.id)
          from n where n.articulo_id = r.articulo_id) as codigos_de_la_ficha,
       exists (select 1 from n
                where n.nom = regexp_replace(translate(lower(btrim(coalesce(
                      r.texto_descripcion,''))),'áéíóúüñ','aeiouun'), '\s+',' ','g')
                  and coalesce(r.texto_descripcion,'') <> '') as matchea_por_nombre,
       case
         when r.articulo_id is null then 'sin identificar: no hay ficha que buscar'
         when not exists (select 1 from n where n.articulo_id = r.articulo_id)
              then 'el cliente NO tiene ficha de este articulo'
         when not exists (select 1 from n where n.articulo_id = r.articulo_id
                            and n.cod is not null and n.cod <> '')
              then 'la ficha existe pero NO tiene codigo cargado'
         else 'la ficha tiene OTRO codigo: viejo o typo'
       end as motivo
from pedidos_renglones r
join pedidos p on p.id = r.pedido_id
join cli on cli.id = p.cliente_id
left join articulos a on a.id = r.articulo_id
where p.anulado_el is null and r.anulado_el is null and r.ficha_id is null
  and coalesce(r.texto_codigo,'') <> ''
  and not exists (
      select 1 from n
       where n.cod = regexp_replace(translate(lower(btrim(r.texto_codigo)),
                     'áéíóúüñ','aeiouun'), '\s+',' ','g'))
order by motivo, articulo, p.fecha_operacion;
