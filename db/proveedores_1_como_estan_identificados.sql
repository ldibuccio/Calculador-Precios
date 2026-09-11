-- ¿CÓMO ESTÁ IDENTIFICADO UN PROVEEDOR, Y HAY DUPLICADOS?
--
-- La identidad de un proveedor de compras es `codigo_puesto`, no el nombre:
-- está UNIQUE en el esquema y `obtener_o_crear_proveedor_por_codigo` busca
-- por ahí y PISA el nombre con el último cargado. El nombre es una etiqueta.
--
-- Por eso las dos preguntas no son la misma:
--   * repetir un CÓDIGO lo impide la base -> `codigos_repetidos` tiene que
--     dar 0, y si no da 0 es que la guarda no está en ESTA base.
--   * repetir un NOMBRE no lo impide nadie -> `nombres_repetidos` puede dar
--     cualquier cosa, y no es necesariamente un error: dos puestos distintos
--     del mismo dueño son dos proveedores de verdad.
--
-- El plegado es EL MISMO del índice de `codigo_cliente` (copiado de
-- db/plegar_tildes_en_codigo_cliente.sql, no reescrito): si algún día se
-- indexa el nombre va a plegar así, y medir con otro daría otro número.
--
-- CONTEOS, con `cuales` de muestra (hasta 10) para poder accionar sin una
-- segunda consulta. Probada con el caso plantado (corolario 36).

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
