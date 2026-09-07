-- Los renglones SIN FICHA del cliente: cuántos son, cuántos vinieron de mail
-- y cuántos podría recuperar un backfill por código.
-- "Recuperable" copia el PRIMER camino de _armar_renglones_pedido_desde_bloque
-- (app/main.py): match EXACTO del texto contra el alias de una ficha del
-- cliente. Los otros dos caminos —nombre exacto y sugerencia difusa— no se
-- replican: el difuso no es determinístico y un backfill no puede adivinar.
-- El normalizado imita normalizar_texto (core/matcheo_comanda.py): minúsculas,
-- sin acentos, sin espacios de más. En SQL PURO, sin unaccent, que hay que
-- habilitar por proyecto y se pierde en la base de la empresa siguiente.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
norm as (
    select fl.id as ficha_id,
           translate(lower(btrim(fl.codigo_cliente)), 'áéíóúüñ', 'aeiouun') as cod,
           translate(lower(btrim(fl.nombre_cliente)), 'áéíóúüñ', 'aeiouun') as nom
    from fichas_logistica fl join cli on cli.id = fl.cliente_id
),
sin_ficha as (
    select r.id, p.origen, (p.mail_message_id is not null) as de_mail,
           r.articulo_id,
           regexp_replace(translate(lower(btrim(coalesce(r.texto_codigo, ''))),
                                    'áéíóúüñ', 'aeiouun'), '\s+', ' ', 'g') as cod,
           regexp_replace(translate(lower(btrim(coalesce(r.texto_descripcion, ''))),
                                    'áéíóúüñ', 'aeiouun'), '\s+', ' ', 'g') as nom
    from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id
    join cli on cli.id = p.cliente_id
    where p.anulado_el is null and r.anulado_el is null and r.ficha_id is null
)
select count(*) as renglones_sin_ficha,
       count(*) filter (where de_mail) as de_mail,
       count(*) filter (where not de_mail) as cargados_a_mano,
       count(*) filter (where articulo_id is not null) as con_articulo_sin_ficha,
       count(*) filter (where articulo_id is null) as sin_identificar,
       count(*) filter (
           where cod <> '' and exists (select 1 from norm n where n.cod = sf.cod)
       ) as recuperables_por_codigo,
       count(*) filter (
           where nom <> '' and exists (select 1 from norm n where n.nom = sf.nom)
       ) as recuperables_por_nombre
from sin_ficha sf;
