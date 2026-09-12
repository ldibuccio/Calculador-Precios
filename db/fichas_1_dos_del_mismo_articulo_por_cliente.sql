-- ¿Hay clientes con DOS fichas del mismo artículo? ¿Y se pueden distinguir?
--
-- El 12/09 Analizar Artículo pasó a elegir CLIENTE y después ARTÍCULO, y su
-- selector lista las FICHAS del cliente: con dos del mismo artículo —Banana
-- Bolivia y Banana Ecuador para Día— cada una es una entrada con su nombre,
-- así que no hay un tercer paso para desambiguar.
--
-- Eso funciona SI las dos se pueden nombrar distinto. `nombre_cliente` es
-- NULLABLE y no hay unique de (articulo_id, cliente_id) —lo dropeó la Parte
-- 3— así que dos fichas del mismo artículo SIN nombre propio se verían las
-- dos como el nombre del artículo, y no habría forma de elegir.
--
-- Por eso son DOS preguntas y no una, y la segunda es la que importa:
--   pares          -> el caso existe (si es 0, no hay nada que mirar)
--   pares_ciegos   -> el caso existe Y LA PANTALLA NO PUEDE MOSTRARLO
-- Un `pares` alto con `pares_ciegos` en 0 es la buena noticia: pasa seguido
-- y cada ficha tiene su nombre.
--
-- `fichas` y `clientes_con_ficha` son la POBLACIÓN: 3 pares sobre 800 fichas
-- y 3 sobre 12 no son el mismo hallazgo, y sin el denominador al lado nadie
-- se acuerda de ir a buscarlo.
--
-- Verificada contra db/esquema_completo.sql en Postgres 16 con el caso
-- plantado: sin nada da 0/0; con dos fichas nombradas del mismo artículo da
-- pares 1 · ciegos 0; borrándoles el nombre, pares 1 · ciegos 1.
with pares as (
  select fl.cliente_id, fl.articulo_id,
         count(*) as cuantas,
         count(distinct coalesce(nullif(btrim(fl.nombre_cliente), ''), '@sin-nombre'))
           as nombres_distintos,
         count(*) filter (where nullif(btrim(fl.nombre_cliente), '') is null)
           as sin_nombre
  from fichas_logistica fl
  group by fl.cliente_id, fl.articulo_id
  having count(*) > 1
)
select
  (select count(*) from pares) as pares,
  -- Ciego = las etiquetas del selector se repetirían: o más de una sin
  -- nombre, o dos con el MISMO nombre propio.
  (select count(*) from pares
    where sin_nombre > 1 or nombres_distintos < cuantas) as pares_ciegos,
  (select max(cuantas) from pares) as el_peor,
  (select count(*) from fichas_logistica) as fichas,
  (select count(distinct cliente_id) from fichas_logistica) as clientes_con_ficha;
