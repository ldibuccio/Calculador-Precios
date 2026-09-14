-- Las filas que `precios_1` cuenta: quiénes son y a qué HORA se escribieron.
--
-- LA COLUMNA QUE DECIDE ES `creado_hora_arg`, y es la hora, no la fecha:
--   * 21:00 o más tarde  -> el reloj del servidor (UTC ya estaba en mañana).
--   * cualquier otra hora -> NO es el reloj. Es un seed o un SQL a mano.
--
-- Y `dias` lo confirma: el reloj produce +1 EXACTO y nunca otra cosa. Un +3 o
-- un −900 no puede ser el reloj por más que la hora dé.
--
-- DE LAS `fechadas_atras` YA SE SABE, sin correr nada:
-- `db/migracion_clientes_final.sql` siembra 2 conceptos de Día y 2 costos de
-- envase con vigente_desde '2020-01-01' y creado_en = now() de la migración.
-- No es el reloj ni hay nada que arreglar — una vigencia vieja cargada hoy es
-- lo que un seed hace. El seed NO explica las `fechadas_adelante`: su fecha es
-- pasada, así que no puede producir una fila fechada mañana.
--
-- Y LOS NÚMEROS DAN IGUAL EN LAS DOS BASES con distinta cantidad de filas
-- porque `scripts/copiar_catalogo_empresa.py` copia estas dos tablas con
-- `SELECT *`: `creado_en` y `vigente_desde` viajan TAL CUAL. No es uso.
--
-- El `values` + `left join` hace que una tabla LIMPIA devuelva su fila igual,
-- en NULL. Verificada contra db/esquema_completo.sql con tres casos plantados
-- (reloj, seed, y una fila sana que NO tiene que aparecer).
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
