WITH tz AS (SELECT 'America/Argentina/Buenos_Aires' z),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id, fecha_operacion
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC),
arm AS (
  SELECT r.id, r.articulo_id, v.fecha_operacion f_pedido,
         (r.armado_el AT TIME ZONE (SELECT z FROM tz))::date f_tilde,
         COALESCE(r.cantidad_armada, r.cantidad) bultos
  FROM pedidos_renglones r JOIN vig v ON v.id = r.pedido_id
  WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id IS NOT NULL),
dif AS (SELECT *, (f_tilde - f_pedido) d FROM arm),
riesgo AS (
  SELECT count(*) n, COALESCE(sum(x.bultos), 0) b
  FROM dif x
  WHERE x.d > 0 AND EXISTS (
    SELECT 1 FROM compras c
    WHERE c.articulo_id = x.articulo_id AND c.estado = 'recepcionado'
      AND COALESCE((c.procesada_el AT TIME ZONE (SELECT z FROM tz))::date,
                   c.fecha_operacion) > x.f_pedido
      AND COALESCE((c.procesada_el AT TIME ZONE (SELECT z FROM tz))::date,
                   c.fecha_operacion) <= x.f_tilde))
SELECT 'fecha_armado_1_cuanto_esta_corrido' QUE_CONSULTA,
  count(*) FILTER (WHERE d <> 0) RENGLONES_CORRIDOS,
  count(*) renglones_armados_TOTALES,
  COALESCE(sum(bultos) FILTER (WHERE d <> 0), 0) BULTOS_CORRIDOS,
  COALESCE(sum(bultos), 0) bultos_armados_totales,
  count(*) FILTER (WHERE d > 0) tildados_DESPUES,
  count(*) FILTER (WHERE d < 0) tildados_ANTES,
  count(*) FILTER (WHERE d = 1) corridos_1_dia,
  count(*) FILTER (WHERE d >= 2) corridos_2_o_mas,
  COALESCE(max(d), 0) peor_corrimiento_dias,
  count(DISTINCT f_pedido) FILTER (WHERE d <> 0) DIAS_CON_ALGUN_CORRIDO,
  count(DISTINCT f_pedido) dias_con_armado,
  (SELECT n FROM riesgo) renglones_que_PERDERIAN_LOTE,
  (SELECT b FROM riesgo) bultos_que_PERDERIAN_LOTE,
  (SELECT max(f_pedido) FROM arm) ultimo_armado
FROM dif;

-- ---------------------------------------------------------------------------
-- CUÁNTO ESTÁ CORRIDO EL ARMADO. Se corre SOLA y no escribe nada.
--
-- Hoy el stock resta por `armado_el`, que es CUÁNDO SE TILDÓ. Esta consulta
-- mide cuántos renglones tienen el tilde en un día distinto al del PEDIDO,
-- que es cuándo salió la mercadería.
--
-- LAS COLUMNAS QUE DECIDEN:
--   · RENGLONES_CORRIDOS sobre `renglones_armados_TOTALES` — si el primero es
--     del orden del segundo, esto es sistemático y todos los días del sistema
--     están corridos. Si es un puñado, es el caso de VL y nada más.
--   · BULTOS_CORRIDOS — el tamaño, en bultos, de lo que hoy cae en el día
--     equivocado.
--   · DIAS_CON_ALGUN_CORRIDO sobre `dias_con_armado` — cuántas fechas del
--     sistema tienen al menos un renglón en el día que no es.
--   · tildados_DESPUES / tildados_ANTES — el primero es el caso normal (se
--     tilda al otro día); el segundo no debería existir y si aparece es otra
--     cosa que hay que mirar aparte.
--
-- Y LA QUE MIDE EL RIESGO DEL FIFO, que es la razón de que esta consulta no
-- sea solo un conteo: `renglones_que_PERDERIAN_LOTE` cuenta los renglones
-- que se moverían a un día ANTERIOR a la recepción del lote que hoy los
-- cubre. Esos pasan a `sin_lote` con el cambio — la mercadería salió igual,
-- pero el papel que hoy la explica deja de poder explicarla.
--
-- PROBADA contra db/esquema_completo.sql en Postgres 16, con las dos
-- respuestas y el control (corolario 53):
--     el caso   3 corridos de 5 · 35 bultos · 2 después · 1 antes · 1 pierde lote
--     control   0 corridos · 0 bultos · 0 antes · 0 pierden lote
-- Y el `1 pierde lote / 20 bultos` coincide EXACTO con el `sin_lote 20` que
-- devuelve `repartir_fifo` sobre el mismo caso: las dos fuentes chocan y
-- dicen lo mismo (corolario 19).
