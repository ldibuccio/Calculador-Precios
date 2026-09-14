-- Las filas que `precios_1` cuenta: quiénes son y a qué HORA se escribieron.
--
-- BASELINE CONFIRMADO el 14/09, corrido en las DOS bases y con los MISMOS
-- números. No hay nada que volver a investigar acá:
--   * 4 ATRÁS = EL SEED de db/migracion_clientes_final.sql: vigente_desde
--     2020-01-01, creado_en 30/07 00:06, dias −2402, las cuatro del mismo
--     timestamp. Nada que arreglar.
--   * 5 ADELANTE = EL RELOJ: 15/08 a las 22:01 de Argentina, dias +1, las
--     cinco del mismo creado_en — las cinco tasas de UN cliente (Grupo L en
--     Frutamax, Taylem en Palmala) cargadas pasadas las diez de la noche.
--     NO SE TOCARON: esas fechas ya pasaron y corregirlas reescribe historia
--     a cambio de nada. El código no puede repetirlo desde el 14/09: los
--     escritores reciben la fecha argentina por parámetro.
--   * precios_venta_historial: LIMPIA, cero y cero en las dos bases.
--
-- Números iguales con distinta cantidad de filas no es uso:
-- scripts/copiar_catalogo_empresa.py las copia con `SELECT *` — creado_en y
-- vigente_desde viajan tal cual.
--
-- LA COLUMNA QUE DECIDE ES `creado_hora_arg`, la HORA y no la fecha: 21:00 o
-- más tarde es el reloj (en UTC ya era mañana); otra hora es un seed o un SQL
-- a mano. Y `dias` lo confirma: el reloj da +1 EXACTO y nunca otra cosa.
--
-- Una tabla limpia devuelve su fila igual, en NULL. Verificada contra
-- db/esquema_completo.sql con casos plantados.
with tablas (tabla) as (
    values ('clientes_parametros_historial'), ('envases_costo_historial')
),
ofensores as (
    select 'clientes_parametros_historial' as tabla,
           c.nombre || ' · ' || h.nombre_parametro as quien,
           h.tipo as detalle, h.valor, h.vigente_desde, h.creado_en
    from clientes_parametros_historial h
    join clientes c on c.id = h.cliente_id
    union all
    select 'envases_costo_historial', e.nombre, 'costo', h.costo,
           h.vigente_desde, h.creado_en
    from envases_costo_historial h
    join envases e on e.id = h.envase_id
)
select
    t.tabla, o.quien, o.detalle, o.valor, o.vigente_desde,
    (o.creado_en at time zone 'America/Argentina/Buenos_Aires') as creado_hora_arg,
    o.vigente_desde
      - (o.creado_en at time zone 'America/Argentina/Buenos_Aires')::date as dias
from tablas t
left join ofensores o
       on o.tabla = t.tabla
      and o.vigente_desde
          <> (o.creado_en at time zone 'America/Argentina/Buenos_Aires')::date
order by t.tabla, o.creado_en, o.quien;
