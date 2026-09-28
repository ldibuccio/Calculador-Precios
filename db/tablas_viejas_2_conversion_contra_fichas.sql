select 'tablas_viejas_2' as QUE_CONSULTA,
       count(*) as filas_viejas,
       count(f.id) as con_ficha,
       count(f.id) filter (where f.nombre_cliente is not distinct from c.nombre_cliente
                           and f.codigo_cliente is not distinct from c.codigo_cliente) as alias_igual,
       count(f.id) filter (where f.nombre_cliente is distinct from c.nombre_cliente
                           or f.codigo_cliente is distinct from c.codigo_cliente) as alias_distinto,
       count(*) - count(f.id) as sin_ficha,
       (select count(*) from fichas_logistica where nombre_cliente is not null) as fichas_con_alias
from conversion_articulos_cliente c
left join fichas_logistica f
       on f.articulo_id = c.articulo_id and f.cliente_id = c.cliente_id;

-- SOLO FRUTAMAX (en Palmala la tabla no existe y esto da error, que es la
-- respuesta). Contesta si los 31 alias de la tabla vieja ya están en las
-- fichas, que es a donde los mudó db/fusionar_conversion_en_fichas.sql.
--
-- alias_igual = filas_viejas: la tabla es un respaldo exacto y se puede
-- borrar. alias_distinto > 0: la ficha cambió después (alguien editó el alias)
-- y la ficha es la que manda, porque es la que lee el código. sin_ficha > 0:
-- ese alias no tiene a dónde ir; hay que mirarlo antes de borrar.
