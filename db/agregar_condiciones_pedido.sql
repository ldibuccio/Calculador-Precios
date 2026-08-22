-- ============================================================================
-- CONDICIONES DE PEDIDO POR CLIENTE + CIERRE DE DÍAS SIN PEDIDO (etapa 3, tramo 2)
-- ============================================================================
-- Dos tablas para el tramo 2 (revisión automática + alertas):
--
-- 1. clientes_condiciones_pedido: qué días de la semana se ESPERA pedido de
--    cada cliente — alimenta la alerta "Falta el pedido". Arranca SOLO con
--    dias_esperados: acá van únicamente condiciones que dirigen
--    comportamiento; lo que el dato mismo ya dice (OC, totales, códigos) no
--    se duplica en flags — un flag que se desactualiza es peor que no
--    tenerlo. usa_sucursales se sumará cuando se construya lo que lo lea.
--
-- 2. dias_sin_pedido: el cierre manual de un día esperado que quedó sin
--    pedido (feriado, el cliente no pidió). Sin esto la alerta de faltantes
--    queda prendida para siempre y en dos semanas se ignora. La alerta se
--    cierra de DOS formas: cargando el pedido, o con esta marca.
--
-- ADITIVO PURO: no modifica ninguna tabla existente. Correr en las DOS
-- bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

create table clientes_condiciones_pedido (
    cliente_id      bigint primary key references clientes (id),
    -- Días de la semana en que se espera pedido, separados por coma
    -- (1=lunes ... 7=domingo), ej. '1,2,3,4,5,6'. NULL = cliente
    -- esporádico: la alerta de pedidos faltantes no aplica y no aparece.
    dias_esperados  text,
    actualizado_en  timestamptz not null default now()
);

comment on table clientes_condiciones_pedido is
    'Condiciones de pedido por cliente (hoy: solo los días esperados, para la alerta de faltantes). Solo condiciones que dirigen comportamiento: lo que el dato mismo ya dice no se duplica en flags.';

create table dias_sin_pedido (
    id             bigint generated always as identity primary key,
    cliente_id     bigint not null references clientes (id),
    fecha          date not null,
    -- Por qué no hubo pedido ese día (feriado, el cliente no pidió). Opcional.
    motivo         text,
    registrado_en  timestamptz not null default now(),
    unique (cliente_id, fecha)
);

comment on table dias_sin_pedido is
    'Cierre manual de un día esperado SIN pedido: la alerta de faltantes deja de contarlo. Si después aparece un pedido para esa fecha, el pedido manda y la marca queda de registro sin efecto. Marca administrativa: se puede deshacer (borrar) mientras no haya pedido.';

-- Verificación: las dos tablas creadas.
-- select table_name from information_schema.tables
-- where table_name in ('clientes_condiciones_pedido', 'dias_sin_pedido');
