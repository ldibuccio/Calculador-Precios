WITH tz AS (SELECT 'America/Argentina/Buenos_Aires' z, DATE '2026-09-17' tope)
SELECT 'arandano_4_cual_filtro_tira_el_renglon' QUE_CONSULTA,
  r.sucursal, r.pedido_id, cl.nombre cliente, p.fecha_operacion,
  r.articulo_id, a.nombre articulo, r.texto_codigo, r.texto_descripcion,
  r.cantidad pedida, r.cantidad_armada armada,
  (r.armado_el AT TIME ZONE (SELECT z FROM tz))::date armado_el,
  CASE
    WHEN r.articulo_id IS NULL          THEN 'SIN IDENTIFICAR (articulo_id NULL)'
    WHEN r.armado_el IS NULL            THEN 'SIN ARMAR (armado_el NULL)'
    WHEN r.anulado_el IS NOT NULL       THEN 'RENGLON ANULADO'
    WHEN (r.armado_el AT TIME ZONE (SELECT z FROM tz))::date > (SELECT tope FROM tz)
                                        THEN 'ARMADO DESPUES DEL CORTE'
    WHEN COALESCE(r.cantidad_armada, r.cantidad) < r.cantidad
                                        THEN 'CUENTA MENOS: se armo ' ||
                                             COALESCE(r.cantidad_armada, r.cantidad) ||
                                             ' de ' || r.cantidad
    ELSE 'cuenta entero' END POR_QUE,
  CASE WHEN r.articulo_id IS NULL OR r.armado_el IS NULL OR r.anulado_el IS NOT NULL
         OR (r.armado_el AT TIME ZONE (SELECT z FROM tz))::date > (SELECT tope FROM tz)
       THEN 0 ELSE COALESCE(r.cantidad_armada, r.cantidad) END LO_QUE_RESTA_DEL_STOCK,
  p.armado_cerrado_el, r.ficha_id, r.agregado_a_mano_el, r.cantidad_original
FROM pedidos_renglones r
JOIN pedidos p ON p.id = r.pedido_id
LEFT JOIN articulos a ON a.id = r.articulo_id
LEFT JOIN clientes cl ON cl.id = p.cliente_id
WHERE p.fecha_operacion = (SELECT tope FROM tz)
  AND p.anulado_el IS NULL
  AND (lower(COALESCE(a.nombre, '')) LIKE 'ar%nd%n%'
    OR lower(COALESCE(r.texto_descripcion, '')) LIKE '%ar%nd%n%'
    OR lower(COALESCE(r.texto_codigo, '')) LIKE '%ar%nd%n%')
ORDER BY r.sucursal;

-- ---------------------------------------------------------------------------
-- CUÁL FILTRO TIRA EL RENGLÓN. Se corre SOLA y no escribe nada.
--
-- El stock resta los armados con ESTOS CUATRO filtros (`salidas` en
-- `_SQL_SUMAS_STOCK`, app/db.py), más un COALESCE que puede restar de menos:
--     r.articulo_id IS NOT NULL
--     r.armado_el   IS NOT NULL
--     r.anulado_el  IS NULL
--     (r.armado_el AT TIME ZONE 'America/...')::date <= la fecha mirada
--     SUM(COALESCE(r.cantidad_armada, r.cantidad))
--
-- LAS CINCO FORMAS DAN EL MISMO NÚMERO, medido corriendo `_sql_sumas_stock`
-- IMPORTADA sobre un pedido con tres sucursales de 10: las cinco devuelven
-- salidas 20 y stock −8, contra 30 y −18 del control. Por eso el total no
-- alcanza para saber cuál es, y esta consulta mira el RENGLÓN.
--
-- NO HACE JOIN POR `articulo_id`, y eso no es un detalle: un renglón SIN
-- IDENTIFICAR tiene `articulo_id` NULL, así que un `JOIN articulos` lo
-- esconde — justamente el caso que se está buscando. Por eso busca por
-- artículo O por el texto de la comanda, y el JOIN es LEFT.
--
-- `LO_QUE_RESTA_DEL_STOCK` da 0 cuando un filtro lo tira, así que la columna
-- SUMA EXACTAMENTE lo que la función real resta. Verificado en tres
-- escenarios: 30/30, 20/20 y 20/20. Si la suma no cuadra contra la pantalla,
-- lo que falta está afuera de este pedido.
--
-- LO QUE QUEDÓ DESCARTADO por lectura del SQL real, para no volver a
-- buscarlo: la cuenta NO mira `armado_cerrado_el`, NO toca
-- `pedidos_sucursales` y NO nombra `sucursal`. Que el pedido esté terminado
-- no le saca ni le pone nada.
--
-- PROBADA contra db/esquema_completo.sql en Postgres 16 con las SEIS
-- variantes plantadas (completo, sin armar, anulado, sin identificar,
-- armado 0 de 10, armado al día siguiente): devuelve las seis respuestas
-- distintas y VL aparece en las seis. Un detector que no puede dar todas
-- las respuestas no sirve (corolario 53).
