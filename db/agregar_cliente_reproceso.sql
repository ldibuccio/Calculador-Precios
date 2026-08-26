-- ============================================================================
-- REPROCESO CON CLIENTE (decisión del 25/08)
-- ============================================================================
-- La primera de un reproceso se arma PARA un cliente (cajas de 6 kg para
-- Día). Se guarda el cliente en la guía R como DATO: trazabilidad ("armada
-- para Día" en Guías R y en el detalle FIFO) y vigilancia — la alerta de
-- Auditoría canta cuando la atribución FIFO detecta bultos de una primera
-- armada para un cliente saliendo en pedidos de OTRO. Aviso con datos,
-- nunca traba.
--
-- El stock NO cambia: sigue siendo derivado, por artículo y sin dueño. Si
-- algún día un producto tiene presentaciones realmente distintas por
-- cliente, eso son ARTÍCULOS separados (camino ya validado con Papa
-- Elegida / Papa Negra), no stock con dueño.
--
-- Las guías R ya cargadas quedan con cliente NULL = "sin cliente" (guías
-- viejas): no participan de la alerta de cruce.
--
-- ADITIVO PURO: no modifica filas existentes. Correr en las DOS bases
-- (Frutamax y Palmala) y marcar en APLICADO.md. El código que usa esta
-- columna se mergea recién después de la confirmación.
-- ============================================================================

alter table reprocesos
    add column cliente_id bigint references clientes(id);

comment on column reprocesos.cliente_id is
    'Para quién se armó la primera (dato de trazabilidad: el stock sigue sin dueño). NULL = guía vieja, sin cliente. La alerta de Auditoría cruza este cliente contra el de los pedidos que el FIFO atribuye a esta primera.';

-- Verificación: la columna creada.
-- select column_name from information_schema.columns
--  where table_name = 'reprocesos' and column_name = 'cliente_id';
