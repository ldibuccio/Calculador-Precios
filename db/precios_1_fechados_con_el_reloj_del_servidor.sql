-- ¿Quedaron filas de vigencia fechadas con el reloj del SERVIDOR de la base?
--
-- Hasta el 14/09 los INSERT de las tres tablas de historial decían
-- CURRENT_DATE (fecha del servidor) y las lecturas resuelven el vigente con
-- la fecha ARGENTINA. Con la base en UTC se separan a partir de las 21:00 de
-- Argentina: lo cargado a esa hora quedaba fechado MAÑANA, sin error y sin
-- regir el día en que se cargó.
--
-- LA COLUMNA QUE DECIDE ES `fechadas_adelante`. Las dos de contexto solo
-- difieren entre las 21:00 y la medianoche, así que verlas iguales no prueba
-- nada. `fechadas_atras` en PRECIOS es la carga retroactiva, legítima desde
-- el 14/09; en las otras dos no hay forma de cargar con fecha, así que ahí
-- cualquier número distinto de cero es otra cosa.
--
-- El `values` + `left join` está para que una tabla VACÍA devuelva su fila en
-- cero en vez de desaparecer. Verificada contra db/esquema_completo.sql en
-- Postgres 16, con el caso plantado en las tres y con el control vacío.
with tablas (tabla) as (
    values ('precios_venta_historial'),
           ('envases_costo_historial'),
           ('clientes_parametros_historial')
),
filas as (
    select 'precios_venta_historial' as tabla, vigente_desde, creado_en
    from precios_venta_historial
    union all
    select 'envases_costo_historial', vigente_desde, creado_en
    from envases_costo_historial
    union all
    select 'clientes_parametros_historial', vigente_desde, creado_en
    from clientes_parametros_historial
)
select
    t.tabla,
    (now() at time zone 'America/Argentina/Buenos_Aires')::date as hoy_argentina,
    current_date                                                as hoy_del_servidor,
    count(f.vigente_desde)                                      as filas_total,
    count(*) filter (
        where f.vigente_desde
              > (f.creado_en at time zone 'America/Argentina/Buenos_Aires')::date
    )                                                           as fechadas_adelante,
    count(*) filter (
        where f.vigente_desde
              < (f.creado_en at time zone 'America/Argentina/Buenos_Aires')::date
    )                                                           as fechadas_atras,
    max((f.creado_en at time zone 'America/Argentina/Buenos_Aires')::date)
                                                                as ultima_carga
from tablas t
left join filas f on f.tabla = t.tabla
group by t.tabla
order by t.tabla;
