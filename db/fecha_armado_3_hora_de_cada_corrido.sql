WITH tz AS (SELECT 'America/Argentina/Buenos_Aires' z),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id, cliente_id, fecha_operacion
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC)
SELECT 'fecha_armado_3_hora_de_cada_corrido' QUE_CONSULTA,
  v.fecha_operacion FECHA_DEL_PEDIDO,
  to_char(r.armado_el AT TIME ZONE (SELECT z FROM tz), 'DD/MM HH24:MI') TILDE_ARGENTINA,
  to_char(r.armado_el AT TIME ZONE 'UTC', 'DD/MM HH24:MI') tilde_UTC,
  ((r.armado_el AT TIME ZONE (SELECT z FROM tz))::date - v.fecha_operacion) DIAS_CORRIDO,
  CASE WHEN extract(hour FROM (r.armado_el AT TIME ZONE (SELECT z FROM tz))) >= 21
       THEN 'DE NOCHE — la zona lo explicaria'
       ELSE 'no es de noche — la zona NO lo explica' END LA_ZONA_LO_EXPLICA,
  cl.nombre cliente, r.sucursal, a.nombre articulo,
  COALESCE(r.cantidad_armada, r.cantidad) bultos,
  to_char(p.creado_en AT TIME ZONE (SELECT z FROM tz), 'DD/MM HH24:MI') pedido_cargado,
  to_char(p.armado_cerrado_el AT TIME ZONE (SELECT z FROM tz), 'DD/MM HH24:MI') armado_cerrado,
  -- IDENTIDAD DE LA BASE (corolario 17). Sin esto, dos bases distintas
  -- imprimen filas indistinguibles y no hay forma de saber si se corrió dos
  -- veces la misma: pasó el 19/09 con siete filas idénticas.
  (SELECT count(*) FROM articulos) arts_en_la_base,
  (SELECT count(*) FROM clientes) clientes_en_la_base,
  (SELECT count(*) FROM pedidos WHERE anulado_el IS NULL) pedidos_vivos_en_la_base
FROM pedidos_renglones r
JOIN vig v ON v.id = r.pedido_id
JOIN pedidos p ON p.id = r.pedido_id
LEFT JOIN clientes cl ON cl.id = v.cliente_id
LEFT JOIN articulos a ON a.id = r.articulo_id
WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id IS NOT NULL
  AND (r.armado_el AT TIME ZONE (SELECT z FROM tz))::date <> v.fecha_operacion
ORDER BY DIAS_CORRIDO DESC, v.fecha_operacion DESC
LIMIT 60;

-- ---------------------------------------------------------------------------
-- LA HORA EXACTA DE CADA RENGLÓN CORRIDO, en argentina y en UTC al lado.
-- Se corre SOLA y no escribe nada. Hasta 60 filas, las más corridas primero.
--
-- `LA_ZONA_LO_EXPLICA` dice, renglón por renglón, si el tilde cae después de
-- las 21 hora argentina — que es la única franja en la que un día leído en
-- UTC sale distinto del día leído acá.
--
-- `pedido_cargado` y `armado_cerrado` van al lado para poder distinguir un
-- tilde tardío de un pedido cargado tarde: si el pedido se cargó el 18 y
-- dice fecha_operacion del 17, el corrimiento no es del tilde.
--
-- PROBADA contra db/esquema_completo.sql con los dos casos plantados: un
-- tilde de 09:30 y otro de 11:00 salen 'la zona NO lo explica', y uno de las
-- 22:00 argentina —01:00 UTC del día siguiente— sale 'DE NOCHE'. Un detector
-- que no puede dar las dos respuestas no sirve (corolario 53).
