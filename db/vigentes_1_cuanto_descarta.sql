WITH tz AS (SELECT 'America/Argentina/Buenos_Aires' z),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC),
vivos AS (
  SELECT cliente_id, fecha_operacion, count(*) n
  FROM pedidos WHERE anulado_el IS NULL
  GROUP BY 1, 2),
armado AS (
  SELECT r.pedido_id, p.cliente_id, p.fecha_operacion,
         SUM(COALESCE(r.cantidad_armada, r.cantidad)) bultos,
         bool_or(v.id IS NOT NULL) la_ve
  FROM pedidos_renglones r
  JOIN pedidos p ON p.id = r.pedido_id
  LEFT JOIN vig v ON v.id = r.pedido_id
  WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL
    AND p.anulado_el IS NULL AND r.articulo_id IS NOT NULL
  GROUP BY 1, 2, 3)
SELECT 'vigentes_1_cuanto_descarta' QUE_CONSULTA,
  (SELECT count(*) FROM vivos WHERE n > 1) DIAS_CLIENTE_CON_VARIOS_VIVOS,
  (SELECT count(*) FROM vivos) dias_cliente_totales,
  (SELECT COALESCE(sum(n - 1), 0) FROM vivos WHERE n > 1) pedidos_DESCARTADOS,
  (SELECT count(*) FROM pedidos WHERE anulado_el IS NULL) pedidos_vivos,
  (SELECT COALESCE(sum(bultos), 0) FROM armado WHERE NOT la_ve) BULTOS_ARMADOS_QUE_NO_SE_CUENTAN,
  (SELECT COALESCE(sum(bultos), 0) FROM armado) bultos_armados_totales,
  (SELECT COALESCE(max(n), 0) FROM vivos) peor_dia,
  (SELECT count(*) FROM pedidos
     WHERE anulado_el IS NULL AND reemplaza_a_pedido_id IS NOT NULL) recargas_vivas,
  (SELECT count(*) FROM pedidos p WHERE p.anulado_el IS NULL
     AND EXISTS (SELECT 1 FROM pedidos q
                  WHERE q.cliente_id = p.cliente_id
                    AND q.fecha_operacion = p.fecha_operacion
                    AND q.anulado_el IS NULL AND q.id <> p.id)
     AND p.mail_message_id IS NOT NULL) vivos_DUPLICADOS_que_vinieron_por_MAIL,
  (SELECT max(fecha_operacion) FROM pedidos WHERE anulado_el IS NULL) ultimo_pedido;

-- ---------------------------------------------------------------------------
-- CUÁNTO DESCARTA la regla de pedidos vigentes. Se corre SOLA y no escribe nada.
--
-- QUÉ PASA. `_SQL_SUMAS_STOCK` (app/db.py) filtra los armados por
--   SELECT DISTINCT ON (cliente_id, fecha_operacion) id FROM pedidos
--   WHERE anulado_el IS NULL ORDER BY cliente_id, fecha_operacion, creado_en DESC
-- o sea que de todos los pedidos VIVOS de un cliente en un día se queda con
-- UNO —el último cargado— y descarta el resto como si fueran reemplazados.
--
-- Tres OC del mismo súper el mismo día, una por sucursal, son TRES pedidos
-- vivos. La regla cuenta uno: 10 bultos de 30.
--
-- LAS COLUMNAS QUE DECIDEN:
--   · BULTOS_ARMADOS_QUE_NO_SE_CUENTAN — mercadería que salió del galpón y
--     el stock no restó. Es el tamaño del error, en bultos.
--   · DIAS_CLIENTE_CON_VARIOS_VIVOS sobre `dias_cliente_totales` — si el
--     primero es del orden del segundo, esto no es un borde.
--   · vivos_DUPLICADOS_que_vinieron_por_MAIL — la que dice qué son. El
--     índice `pedidos_mail_message_id_unico` impide cargar DOS VECES el
--     mismo mail, así que dos vivos con mail son dos mails DISTINTOS: dos
--     OC reales, no un duplicado. Si esta columna es ~ `pedidos_DESCARTADOS`,
--     lo que la regla tira son pedidos legítimos.
--   · recargas_vivas — el control. Una recarga bien hecha anula el viejo en
--     la misma transacción (`crear_pedido`), así que NO necesita el
--     DISTINCT ON para no contarse dos veces.
--
-- PROBADA contra db/esquema_completo.sql en Postgres 16 con el caso plantado
-- (tres pedidos vivos del mismo cliente y día con 10 bultos cada uno, más una
-- recarga bien hecha de control): devuelve 20 bultos no contados sobre 37, 2
-- pedidos descartados, peor día 3, y distingue el cliente con tres vivos del
-- que tiene uno solo. Las dos respuestas, no una sola (corolario 53).
