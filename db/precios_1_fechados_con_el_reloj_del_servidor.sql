-- ¿Hay precios fechados con el reloj del SERVIDOR en vez del argentino?
--
-- Hasta el 14/09 el INSERT de precios_venta_historial decía CURRENT_DATE, que
-- es la fecha del servidor de la base, mientras que TODAS las lecturas
-- resuelven el vigente con la fecha argentina. Son dos relojes para el mismo
-- hecho: con la base en UTC se separan a partir de las 21:00 de Argentina, y
-- lo cargado a esa hora quedaba fechado MAÑANA — guardado sin error y sin
-- regir hoy.
--
-- Devuelve CONTEOS y no una lista: así siempre vuelve una fila y el cero se
-- ve. Con la población al lado (precios_total) y un testigo de actividad
-- (ultimo_precio_cargado), para que un cero sobre una base quieta no se lea
-- como "acá no hay problema".
--
-- VERIFICADA CONTRA `db/esquema_completo.sql` EN POSTGRES 16, con el caso
-- plantado (una fila cargada 22:00 de Argentina y fechada al día siguiente)
-- y con el control vacío: da 0 sobre la base limpia y 1 con el caso puesto.
-- Un cero sin eso no se distingue de una consulta que no sabe ver el caso.
--
-- `fechados_atras` es la carga RETROACTIVA, que desde el 14/09 es legítima
-- (ver /precios/cargar): si crece, no es un bug — es la función nueva.
--
-- LA COLUMNA QUE DECIDE ES `fechados_adelante`. Las dos de arriba son el
-- contexto del momento en que se corre: solo difieren entre las 21:00 y la
-- medianoche de Argentina, así que verlas iguales no prueba nada.
select
    (now() at time zone 'America/Argentina/Buenos_Aires')::date   as hoy_argentina,
    current_date                                                  as hoy_del_servidor,
    count(*)                                                      as precios_total,
    count(*) filter (
        where vigente_desde
              > (creado_en at time zone 'America/Argentina/Buenos_Aires')::date
    )                                                             as fechados_adelante,
    count(*) filter (
        where vigente_desde
              < (creado_en at time zone 'America/Argentina/Buenos_Aires')::date
    )                                                             as fechados_atras,
    max((creado_en at time zone 'America/Argentina/Buenos_Aires')::date)
                                                                  as ultimo_precio_cargado
from precios_venta_historial;
