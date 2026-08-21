-- ============================================================================
-- PEDIDOS DE CLIENTES (etapa 1: carga pegando el texto del mail)
-- ============================================================================
-- El pedido de Día llega por mail al mediodía, con tres sucursales (VL,
-- BZ, GR), cada una con su número de orden de compra y su total de bultos
-- declarado. El pedido es DEMANDA: sin ninguna FK contra compras (la
-- compra es oferta; se cruzan en vivo por artículo y fecha).
--
-- Invariante duro: lo que el mail dice se guarda ENTERO. Un renglón cuyo
-- código no matchea ninguna ficha se guarda igual, con su texto crudo y
-- articulo_id NULL ("sin identificar"), para asignarlo después. Nada se
-- descarta en silencio.
--
-- ADITIVO PURO: no modifica ninguna tabla existente. Correr en las DOS
-- bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

create table pedidos (
    id                     bigint generated always as identity primary key,
    cliente_id             bigint not null references clientes (id),
    fecha_operacion        date not null,
    origen                 text not null check (origen in ('texto', 'mail')),
    -- El texto pegado tal cual (etapa 3: el cuerpo del mail). Es el
    -- respaldo último para auditar qué leyó la IA contra qué llegó.
    texto_original         text,
    -- Etapa 3: cuándo llegó el mail y su Message-ID (idempotencia: cada
    -- mail se procesa UNA sola vez). En etapa 1 quedan NULL.
    recibido_el            timestamptz,
    mail_message_id        text,
    -- Un pedido corregido se carga como pedido NUEVO apuntando al viejo,
    -- y el viejo se anula (baja lógica, nunca DELETE). El link permite
    -- mostrar el diff contra el anterior y trasladar los tildes de
    -- armado de los renglones idénticos (ver etapa 2).
    reemplaza_a_pedido_id  bigint references pedidos (id),
    creado_en              timestamptz not null default now(),
    anulado_el             timestamptz
);

comment on table pedidos is
    'Cabecera del pedido diario de un cliente (Dia llega por mail ~12:00). Demanda pura: sin FK contra compras. Un pedido corregido es una fila nueva con reemplaza_a_pedido_id; el viejo se anula (anulado_el), nunca se pisa.';

create unique index pedidos_mail_message_id_unico
    on pedidos (mail_message_id) where mail_message_id is not null;
create index pedidos_cliente_fecha_idx on pedidos (cliente_id, fecha_operacion);

create table pedidos_sucursales (
    id                      bigint generated always as identity primary key,
    pedido_id               bigint not null references pedidos (id),
    sucursal                text not null,
    -- La OC de Dia por sucursal: hace falta para facturar (ya hay mails
    -- de Dia reclamando OC faltantes). Texto, no numero: puede traer
    -- ceros a la izquierda o cambiar de formato.
    orden_compra            text,
    -- El total de bultos que DECLARA el mail para esa sucursal. Control
    -- cruzado: si la suma de lo leido no coincide, la pantalla avisa
    -- fuerte — asi un numero mal leido por la IA se detecta solo.
    total_bultos_declarado  numeric,
    unique (pedido_id, sucursal)
);

comment on table pedidos_sucursales is
    'Una fila por sucursal del pedido (VL/BZ/GR de Dia — texto libre, sin CHECK: pueden cambiar), con su orden de compra y el total de bultos declarado en el mail para el control cruzado.';

create table pedidos_renglones (
    id                bigint generated always as identity primary key,
    pedido_id         bigint not null references pedidos (id),
    -- La sucursal de este renglon. NULL solo para un renglon que vino sin
    -- ninguna cantidad (se guarda igual: nada se pierde).
    sucursal          text,
    -- NULL = "sin identificar": el codigo no matcheo ninguna ficha. El
    -- renglon queda con su texto crudo y se asigna despues.
    articulo_id       bigint references articulos (id),
    -- El texto CRUDO del mail, siempre — aunque haya matcheado: es el
    -- respaldo para auditar el matcheo.
    texto_codigo      text,
    texto_descripcion text,
    cantidad          numeric not null default 0,
    -- Etapa 2 (armado): cuando el deposito tilda el renglon como armado.
    -- En etapa 1 queda NULL.
    armado_el         timestamptz,
    creado_en         timestamptz not null default now()
);

comment on table pedidos_renglones is
    'Un renglon por articulo Y sucursal (una linea del mail con cantidades en VL y GR son dos renglones). articulo_id NULL = sin identificar, con el texto crudo conservado. armado_el lo usa la etapa 2 (tilde de armado del deposito).';

create index pedidos_renglones_pedido_idx on pedidos_renglones (pedido_id);
-- Parcial para la alerta de Auditoria ("pedidos con renglones sin identificar").
create index pedidos_renglones_sin_identificar_idx
    on pedidos_renglones (pedido_id) where articulo_id is null;

-- Respaldo visual: foto/captura del mail original, comprimida con el
-- mismo pipeline que las comandas. Tabla propia desde el dia uno (la
-- leccion de compras.foto_ruta: una columna suelta despues cuesta jubilarla).
create table fotos_pedido (
    id         bigint generated always as identity primary key,
    pedido_id  bigint not null references pedidos (id),
    foto_ruta  text not null,
    creado_en  timestamptz not null default now(),
    unique (pedido_id, foto_ruta)
);

comment on table fotos_pedido is
    'Capturas del mail original del pedido, como respaldo visual. Mismo pipeline de compresion que las fotos de comandas.';

-- Verificación: las cuatro tablas creadas.
-- select table_name from information_schema.tables
-- where table_name in ('pedidos', 'pedidos_sucursales', 'pedidos_renglones', 'fotos_pedido');
