-- ¿Hay clientes con DOS fichas del mismo artículo? ¿Y se pueden distinguir?
--
-- AL EDITOR VA SOLO DESDE `with pares as` (855 caracteres). El archivo
-- entero son 3400 y el límite del editor de Supabase es 2500: copiarlo
-- completo es justo la forma de que trunque y pegue SQL ajeno.
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
--
-- CORRIDA EL 12/09, con el nombre de la base adelante (corolario 17), que es
-- lo único que separa dos filas que de otro modo se leen igual:
--
--   Frutamax  pares 0 · ciegos 0 · el_peor NULL · fichas 34 · clientes 2
--   Palmala   pares 1 · ciegos 0 · el_peor 2    · fichas 51 · clientes 3
--
-- Las DOS votan, aunque Palmala esté parada: esto cuenta fichas CARGADAS y no
-- actividad, igual que tildes_1. Por eso la consulta no trae testigo de
-- actividad y no le falta — el denominador hace ese trabajo acá.
--
-- O sea que el caso existe UNA vez, en Palmala, y las dos fichas tienen
-- nombre propio: el selector las distingue y no hay nada que construir.
--
-- Y SI ALGÚN DÍA `pares_ciegos` DA MÁS QUE 0, el arreglo NO es
-- `_desambiguar_cajas`. El patrón sí —desambiguar solo donde choca— pero esa
-- función agrega `_nombre_de_ficha`, que es exactamente lo que la etiqueta
-- del selector ya usa: dos fichas sin nombre quedan en "Banana (Banana)" y
-- "Banana (Banana)", igual de indistinguibles. Verificado corriéndola.
-- El distintivo tiene que ser algo que NO sea el nombre: el codigo_cliente,
-- el contenido_caja o la unidad_venta.
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
