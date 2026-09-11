-- ¿CÓMO ESTÁ IDENTIFICADO UN PROVEEDOR, Y HAY DUPLICADOS?
--
-- La identidad es `codigo_puesto`, no el nombre: está UNIQUE y
-- `obtener_o_crear_proveedor_por_codigo` busca por ahí y PISA el nombre con
-- el último cargado. Por eso las dos preguntas no son la misma: repetir un
-- CÓDIGO lo impide la base (0, o la guarda no está en ESA base); repetir un
-- NOMBRE no lo impide nadie, y no siempre es error — dos puestos del mismo
-- dueño son dos proveedores de verdad.
--
-- El plegado es el del índice de `codigo_cliente`, copiado de
-- db/plegar_tildes_en_codigo_cliente.sql. Probada con el caso plantado (c36).
--
-- CONTESTADA EL 11/09, bases VIVAS (ultima_compra 11/09 en las dos):
-- FRUTAMAX 43/43/0 · PALMALA 32/32/0 · guarda 1 · cod 0 · nom 0.
-- El modelo se sostiene: no hace falta código interno.
--
-- Queda UN agujero: el fantasma por código bien formado pero equivocado
-- (N07P14 por N07P41) — el CHECK valida la forma, no que el puesto exista.
-- Y NO se detecta con `de_baja`: `activo=false` es la salida del fantasma Y
-- la baja normal. Lo que sí los separa: un fantasma no tiene NI UNA COMPRA.

with p as (
  select id, activo, codigo_puesto,
         lower(regexp_replace(translate(btrim(nombre),
           'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüýÿĀāĂăĄąĆćĈĉĊċČčĎďĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĨĩĪīĬĭĮįİĴĵĶķĹĺĻļĽľŃńŅņŇňŌōŎŏŐőŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž',
           'AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuyyAaAaAaCcCcCcCcDdEeEeEeEeEeGgGgGgGgHhIiIiIiIiIJjKkLlLlLlNnNnNnOoOoOoRrRrRrSsSsSsSsTtTtUuUuUuUuUuUuWwYyYZzZzZz'), '\s+', ' ', 'g')) as np
  from proveedores
)
select
  (select count(*) from p) as proveedores,
  (select count(*) from p where activo) as activos,
  (select count(*) from p where not activo) as de_baja,

  (select count(*) from pg_constraint
    where conrelid = 'proveedores'::regclass and contype = 'u') as guarda_codigo_unico,

  (select count(*) from (select 1 from p group by codigo_puesto having count(*) > 1) t)
    as codigos_repetidos,

  (select count(*) from (select 1 from p group by np having count(*) > 1) t)
    as nombres_repetidos,
  (select string_agg(np || ' (' || codigos || ')', ' | ')
     from (select np, string_agg(codigo_puesto, '+') as codigos
             from p group by np having count(*) > 1 limit 10) d) as cuales,

  (select max(fecha_operacion) from compras) as ultima_compra;
