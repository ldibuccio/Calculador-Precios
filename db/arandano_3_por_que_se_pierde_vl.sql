WITH dia AS (SELECT DATE '2026-09-17' f, 'America/Argentina/Buenos_Aires' tz),
arts AS (SELECT id, nombre FROM articulos WHERE lower(nombre) LIKE 'ar%nd%n%'),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC)
SELECT 'arandano_3_por_que_se_pierde_vl' QUE_CONSULTA,
  r.sucursal, r.pedido_id, cl.nombre cliente, p.fecha_operacion,
  r.cantidad pedida, r.cantidad_armada armada,
  (r.armado_el AT TIME ZONE (SELECT tz FROM dia))::date armado_el,
  CASE WHEN r.armado_el IS NULL THEN 'NO ARMADO'
       WHEN r.anulado_el IS NOT NULL THEN 'renglon ANULADO'
       WHEN p.anulado_el IS NOT NULL THEN 'pedido ANULADO'
       WHEN v.id IS NULL THEN 'LO TIRA EL DISTINCT ON'
       ELSE 'cuenta' END POR_QUE,
  COALESCE(r.cantidad_armada, r.cantidad) resta_del_stock,
  (SELECT count(*) FROM pedidos q
    WHERE q.cliente_id = p.cliente_id AND q.fecha_operacion = p.fecha_operacion
      AND q.anulado_el IS NULL) pedidos_VIVOS_ese_dia_del_cliente,
  p.reemplaza_a_pedido_id, p.origen, p.mail_message_id IS NOT NULL vino_por_mail
FROM pedidos_renglones r
JOIN arts x ON x.id = r.articulo_id
JOIN pedidos p ON p.id = r.pedido_id
LEFT JOIN vig v ON v.id = r.pedido_id
LEFT JOIN clientes cl ON cl.id = p.cliente_id
WHERE p.fecha_operacion = (SELECT f FROM dia)
   OR (r.armado_el AT TIME ZONE (SELECT tz FROM dia))::date = (SELECT f FROM dia)
ORDER BY r.sucursal, r.pedido_id;

-- ---------------------------------------------------------------------------
-- POR QUÉ CADA RENGLÓN DE ARÁNDANO DEL 17/09 CUENTA O NO. Se corre sola.
--
-- Lista TODOS los renglones de ese día SIN filtrar por armado ni por vigente,
-- y la columna POR_QUE dice qué lo saca de la cuenta del stock. Eso separa
-- dos causas que se ven igual desde afuera:
--   · 'NO ARMADO'              — el renglón todavía no salió del galpón.
--   · 'LO TIRA EL DISTINCT ON' — salió, y el stock no lo resta.
-- La primera es correcta; la segunda es el error.
--
-- `pedidos_VIVOS_ese_dia_del_cliente` es el denominador: con 1 no hay nada
-- que discutir, con 3 el DISTINCT ON está eligiendo uno de tres.
--
-- Y las dos consultas anteriores (arandano_1 y arandano_2) LLEVAN LA MISMA
-- REGLA ADENTRO, así que su total también cuenta uno de los tres. El de
-- arandano_2 igual los lista todos y los marca con `cuenta_para_el_stock`;
-- el TOTAL de su última fila es el que está recortado.
--
-- PROBADA contra db/esquema_completo.sql con el caso plantado: devuelve las
-- tres sucursales, dos marcadas 'LO TIRA EL DISTINCT ON' y una 'cuenta', más
-- el control de una recarga bien hecha ('pedido ANULADO' + 'cuenta').
