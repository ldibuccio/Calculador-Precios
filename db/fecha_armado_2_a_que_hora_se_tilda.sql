WITH tz AS (SELECT 'America/Argentina/Buenos_Aires' z),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id, fecha_operacion
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC),
arm AS (
  SELECT v.fecha_operacion f_pedido,
         (r.armado_el AT TIME ZONE (SELECT z FROM tz))::date f_arg,
         (r.armado_el AT TIME ZONE 'UTC')::date f_utc,
         extract(hour FROM (r.armado_el AT TIME ZONE (SELECT z FROM tz))) h_arg,
         extract(hour FROM (r.armado_el AT TIME ZONE 'UTC')) h_utc,
         COALESCE(r.cantidad_armada, r.cantidad) bultos
  FROM pedidos_renglones r JOIN vig v ON v.id = r.pedido_id
  WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id IS NOT NULL),
d AS (SELECT *, (f_arg - f_pedido) dif, (f_utc - f_arg) salta_en_utc FROM arm)
SELECT 'fecha_armado_2_a_que_hora_se_tilda' QUE_CONSULTA,
  CASE WHEN dif = 0 THEN 'a) mismo dia'
       WHEN dif = 1 THEN 'b) corrido 1 dia'
       WHEN dif >= 2 THEN 'c) corrido 2 o mas'
       ELSE 'd) tildado ANTES del pedido' END CASO,
  count(*) renglones,
  sum(bultos) bultos,
  count(*) FILTER (WHERE h_arg >= 21) DE_NOCHE_21_a_24_ARG,
  count(*) FILTER (WHERE h_arg < 12) de_manana_0_a_12_arg,
  count(*) FILTER (WHERE h_arg >= 12 AND h_arg < 21) de_tarde_12_a_21_arg,
  count(*) FILTER (WHERE salta_en_utc = 1) EN_UTC_CAEN_AL_DIA_SIGUIENTE,
  min(h_arg) hora_arg_min, max(h_arg) hora_arg_max,
  round(avg(h_arg), 1) hora_arg_promedio,
  min(h_utc) hora_utc_min, max(h_utc) hora_utc_max,
  min(f_pedido) desde, max(f_pedido) hasta
FROM d
GROUP BY 2
ORDER BY 2;

-- ---------------------------------------------------------------------------
-- ¿LOS TILDES CORRIDOS SON DE NOCHE? Se corre SOLA y no escribe nada.
-- Parte los renglones armados en cuatro casos y da, para cada uno, en qué
-- franja horaria ARGENTINA cae el tilde.
--
-- CÓMO SE LEE, y las dos lecturas son opuestas:
--   · si la fila `b) corrido 1 dia` tiene DE_NOCHE_21_a_24_ARG cerca de
--     `renglones`, el corrimiento es de ZONA HORARIA y el arreglo es la
--     conversión, no la fecha que usa el stock;
--   · si tiene `de_manana_0_a_12_arg` cerca de `renglones`, se tilda a la
--     mañana siguiente y el corrimiento es REAL: ahí sí la pregunta es qué
--     fecha tiene que usar el stock.
--
-- `EN_UTC_CAEN_AL_DIA_SIGUIENTE` es el control: cuenta los tildes cuyo día
-- CAMBIA al mirarlos en UTC. Si esos aparecen en la fila `a) mismo dia`, la
-- conversión de producción los está agarrando bien.
--
-- Y UNA COSA QUE NO HACE FALTA MEDIR: un corrimiento de zona horaria es de
-- UN día como máximo, por aritmética. Los `c) corrido 2 o mas` no los puede
-- explicar la zona, sea cual sea el resultado de esta consulta.
--
-- PROBADA contra db/esquema_completo.sql en Postgres 16 con las dos
-- explicaciones plantadas: dos tildes de 21:30 y 22:45 hora argentina (que
-- en UTC saltan al día siguiente) caen en `a) mismo dia` con
-- EN_UTC_CAEN_AL_DIA_SIGUIENTE en 2, y los de la mañana siguiente caen en
-- `b)` y `c)`. O sea que la consulta distingue las dos causas.
