create or replace function vacios_conteo_2809_proveedor(buscado text)
returns table (proveedor_id bigint, iguales int, parecidos int) language sql stable as $f$
  with p as (
    select id, btrim(regexp_replace(replace(translate(lower(nombre), 'áéíóúüñ', 'aeiouun'),
             '.', ''), '[^a-z0-9]+', ' ', 'g')) as f
      from proveedores where activo),
  e as (select id from p where f = buscado),
  c as (select id from p where f ~ ('\m' || buscado || '\M'))
  select case when (select count(*) from e) = 1 then (select min(id) from e)
              when (select count(*) from e) = 0 and (select count(*) from c) = 1
              then (select min(id) from c) end,
         (select count(*)::int from e), (select count(*)::int from c)
$f$;

create or replace function vacios_conteo_2809_marca(prov bigint, marca text)
returns table (marca_id bigint, nombre_actual text, parecidas int, plegado text)
language sql stable as $f$
  with m as (select lower(translate(marca, 'áéíóúñÁÉÍÓÚÑ', 'aeiounAEIOUN')) as mn),
  c as (select v.id, v.nombre, v.nombre_normalizado = m.mn as igual
          from marcas_vacio v, m
         where v.proveedor_id = prov
           and replace(v.nombre_normalizado, ' ', '') = replace(m.mn, ' ', ''))
  select coalesce((select id from c where igual),
                  case when (select count(*) from c) = 1 then (select id from c) end),
         coalesce((select nombre from c where igual),
                  case when (select count(*) from c) = 1 then (select nombre from c) end),
         (select count(*)::int from c), (select mn from m)
$f$;

select 'vacios_conteo_2809_3_buscadores' as que_migracion,
       (select count(*) from pg_proc where proname in
         ('vacios_conteo_2809_proveedor', 'vacios_conteo_2809_marca')) as funciones_2;

-- ARRANQUE DE VACÍOS DEL 28/09, bloque 3. Solo funciones, no escribe datos.
-- El proveedor se busca por nombre plegado: igual exacto, o si no hay, UNO
-- solo que lo contenga como palabras. La marca, plegada y sin espacios:
-- así "Tomjug" es "Tom Jug".
