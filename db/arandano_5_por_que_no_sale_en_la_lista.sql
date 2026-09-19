WITH tz AS (SELECT 'America/Argentina/Buenos_Aires' z, DATE '2026-09-17' dia),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC)
SELECT 'arandano_5_por_que_no_sale_en_la_lista' QUE_CONSULTA,
  r.sucursal, r.pedido_id, cl.nombre cliente, p.fecha_operacion f_pedido,
  to_char(r.armado_el AT TIME ZONE (SELECT z FROM tz), 'DD/MM HH24:MI') tilde_arg,
  r.articulo_id, a.nombre articulo, r.texto_descripcion,
  COALESCE(r.cantidad_armada, r.cantidad) bultos,
  -- LOS CUATRO FILTROS DE fecha_armado_3, uno por columna.
  (r.armado_el IS NOT NULL)      f1_esta_armado,
  (r.anulado_el IS NULL)         f2_no_anulado,
  (r.articulo_id IS NOT NULL)    f3_identificado,
  (v.id IS NOT NULL)             f4_pasa_el_distinct_on,
  CASE WHEN r.armado_el IS NULL   THEN 'LO TIRA f1: no esta armado'
       WHEN r.anulado_el IS NOT NULL THEN 'LO TIRA f2: renglon anulado'
       WHEN r.articulo_id IS NULL THEN 'LO TIRA f3: SIN IDENTIFICAR'
       WHEN v.id IS NULL          THEN 'LO TIRA f4: el DISTINCT ON'
       WHEN (r.armado_el AT TIME ZONE (SELECT z FROM tz))::date = p.fecha_operacion
                                  THEN 'no sale porque NO esta corrido'
       ELSE 'TENDRIA QUE SALIR en fecha_armado_3' END POR_QUE_NO_SALE,
  -- IDENTIDAD DE LA BASE: dos bases no pueden imprimir igual.
  (SELECT count(*) FROM articulos) arts_en_la_base,
  (SELECT count(*) FROM clientes) clientes_en_la_base,
  (SELECT max(fecha_operacion) FROM pedidos WHERE anulado_el IS NULL) ultimo_pedido
FROM pedidos_renglones r
JOIN pedidos p ON p.id = r.pedido_id
LEFT JOIN vig v ON v.id = r.pedido_id
LEFT JOIN articulos a ON a.id = r.articulo_id
LEFT JOIN clientes cl ON cl.id = p.cliente_id
WHERE p.fecha_operacion = (SELECT dia FROM tz)
  AND (lower(COALESCE(a.nombre, '')) LIKE 'ar%nd%n%'
    OR lower(COALESCE(r.texto_descripcion, '')) LIKE '%ar%nd%n%'
    OR lower(COALESCE(r.texto_codigo, '')) LIKE '%ar%nd%n%')
ORDER BY r.sucursal;

-- ---------------------------------------------------------------------------
-- POR QUÉ EL RENGLÓN NO SALE EN fecha_armado_3. Se corre SOLA, no escribe.
--
-- `fecha_armado_3` lista los renglones CORRIDOS y tiene CUATRO filtros que
-- `arandano_4` no tiene. Cualquiera de los cuatro esconde un renglón sin
-- decir por qué, así que esta consulta los evalúa UNO POR COLUMNA sobre los
-- renglones de Arándano del 17/09 — sin ninguno de esos filtros puestos.
--
-- Y LOS CUATRO SON LOS MISMOS QUE LOS DEL STOCK, verificado comparando el
-- texto de `_sql_sumas_stock` IMPORTADA contra el de la consulta: 4 de 4.
--     r.armado_el IS NOT NULL · r.anulado_el IS NULL
--     r.articulo_id IS NOT NULL · JOIN vigentes (DISTINCT ON)
-- Por eso la pregunta "¿por qué no sale en la lista?" y la pregunta "¿por
-- qué el stock no lo resta?" tienen LA MISMA respuesta, y esta consulta la
-- da con nombre.
--
-- CÓMO SE LEE `POR_QUE_NO_SALE`:
--   · 'LO TIRA f1/f2/f3/f4'  — ése es el motivo, y es el mismo por el que el
--     stock cuenta 20 en vez de 30.
--   · 'TENDRIA QUE SALIR en fecha_armado_3' — el renglón está corrido y pasa
--     los cuatro filtros, así que si igual no aparecía en la lista fue el
--     LIMIT 60 y hay que subirlo.
--   · 'no sale porque NO esta corrido' — el tilde cae el mismo día del
--     pedido, y entonces lo que hace que el stock no lo cuente es otra cosa
--     (ver arandano_4).
--
-- LAS TRES ÚLTIMAS COLUMNAS SON LA IDENTIDAD DE LA BASE (corolario 17): dos
-- bases distintas no pueden imprimir filas iguales. Se agregaron el 19/09
-- porque fecha_armado_3 devolvió siete filas idénticas en las dos y no había
-- forma de saber si se había corrido dos veces la misma.
--
-- PROBADA contra db/esquema_completo.sql en Postgres 16 con las CINCO
-- variantes de VL plantadas: nombra f1, f2 y f3 cada una por su nombre, dice
-- 'TENDRIA QUE SALIR' con el renglón armado el 18, y 'NO esta corrido' con
-- el armado el 17. Las cinco respuestas distintas (corolario 53).
