-- ¿HAY DOS PROVEEDORES QUE SEAN EL MISMO, CARGADOS DOS VECES?
--
-- CONTESTADA EL 11/09: NO, ni en Frutamax ni en Palmala. `nombres` dio 0 en
-- las dos. No hay fusiones para hacer y la fusión no se construyó.
--
-- ESTA CONSULTA PERDIÓ DOS CRITERIOS, y por qué se fueron importa más que
-- lo que quedó. Tenía además `a_un_caracter` y `transpuestos` sobre el
-- codigo_puesto, buscando el fantasma por código mal tipeado. Dieron 49
-- pares en Frutamax y 39 en Palmala, y TODOS eran falsos positivos:
--
--   N09P37/N09P36  kleppe | almana s.r.l.
--   N07P41/N08P41  herederos n7 | don ismael
--
-- Nombres sin ninguna relación con códigos vecinos. **Los puestos del
-- mercado son contiguos por diseño**, así que "difieren en un carácter"
-- describe a medio mercado. La heurística no medía parecido: medía
-- vecindad, que acá es la norma y no la excepción.
--
-- Se sacaron en vez de dejarlas: una consulta corrible con criterios que
-- sabemos que no aplican es peor que no tenerlos — la próxima vez que
-- alguien la corra no se va a acordar de que eran ruido.
--
-- Queda el único que apuntaba a la pregunta: dos nombres que se vuelven
-- IGUALES al plegar y colapsar letras repetidas (Dimimax/Dimmimax). El
-- plegado es el del índice de codigo_cliente. Probada con el caso plantado.

with p as (
  select id, codigo_puesto as c,
         lower(regexp_replace(translate(btrim(nombre),
           'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüýÿĀāĂăĄąĆćĈĉĊċČčĎďĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĨĩĪīĬĭĮįİĴĵĶķĹĺĻļĽľŃńŅņŇňŌōŎŏŐőŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž',
           'AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuyyAaAaAaCcCcCcCcDdEeEeEeEeEeGgGgGgGgHhIiIiIiIiIJjKkLlLlLlNnNnNnOoOoOoRrRrRrSsSsSsSsTtTtUuUuUuUuUuUuWwYyYZzZzZz'), '\s+', ' ', 'g')) as np
  from proveedores
), q as (
  select id, c, np, regexp_replace(np, '(.)\1+', '\1', 'g') as nc from p
), m as (
  select a.c as ca, b.c as cb, a.np as na, b.np as nb
  from q a join q b on a.id < b.id
  where a.nc = b.nc and a.np <> b.np
)
select
  (select count(*) from proveedores) as proveedores,
  (select count(*) from m) as nombres_casi_iguales,
  (select string_agg(ca || '/' || cb || ' ' || na || '|' || nb, ' · ')
     from (select * from m limit 10) d) as cuales,
  (select max(fecha_operacion) from compras) as ultima_compra;
