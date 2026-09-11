-- ¿HAY DOS PROVEEDORES QUE SEAN EL MISMO PUESTO MAL TIPEADO?
-- NO está construida: esto mide si hace falta. El porqué, en su commit.
--
-- SQL PURO: levenshtein y similarity son extensiones, y una regla que se
-- pierde al crear la base de la empresa siguiente no es una regla.
--   a_un_caracter: difieren en UNA posición. Firma del fantasma: lo que se
--     tipea mal es el CÓDIGO, no el nombre.
--   transpuestos: dos pegados dados vuelta (N07P41/N07P14), que el de
--     arriba NO ve porque difieren en DOS.
--   nombres: los plegados se igualan al colapsar letras repetidas.
--
-- `cuales` trae SOLO los pares que algún contador marcó. Ninguna prueba
-- nada sola: dos puestos vecinos del mismo dueño difieren en un carácter.
-- Probada con el caso plantado (c36).

with p as (
  select id, codigo_puesto as c,
         lower(regexp_replace(translate(btrim(nombre),
           'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüýÿĀāĂăĄąĆćĈĉĊċČčĎďĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĨĩĪīĬĭĮįİĴĵĶķĹĺĻļĽľŃńŅņŇňŌōŎŏŐőŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž',
           'AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuyyAaAaAaCcCcCcCcDdEeEeEeEeEeGgGgGgGgHhIiIiIiIiIJjKkLlLlLlNnNnNnOoOoOoRrRrRrSsSsSsSsTtTtUuUuUuUuUuUuWwYyYZzZzZz'), '\s+', ' ', 'g')) as np
  from proveedores
), q as (
  select id, c, np, regexp_replace(np, '(.)\1+', '\1', 'g') as nc from p
), pares as (
  select a.c as ca, b.c as cb, a.np as na, b.np as nb,
         (a.nc = b.nc and a.np <> b.np) as nombre_igual,
         (select count(*) from generate_series(1, 6) i
           where substr(a.c, i, 1) <> substr(b.c, i, 1)) as difieren,
         exists (select 1 from generate_series(1, 5) i
                  where substr(a.c, i, 1) = substr(b.c, i + 1, 1)
                    and substr(a.c, i + 1, 1) = substr(b.c, i, 1)
                    and substr(a.c, i, 1) <> substr(a.c, i + 1, 1)) as transpuesto
  from q a join q b on a.id < b.id
), m as (
  select * from pares
   where difieren = 1 or (difieren = 2 and transpuesto) or nombre_igual
)
select
  (select count(*) from proveedores) as proveedores,
  (select count(*) from m where difieren = 1) as a_un_caracter,
  (select count(*) from m where difieren = 2 and transpuesto) as transpuestos,
  (select count(*) from m where nombre_igual) as nombres,
  (select string_agg(ca || '/' || cb || ' ' || na || '|' || nb, ' · ')
     from (select * from m limit 10) d) as cuales,
  (select max(fecha_operacion) from compras) as ultima_compra;
