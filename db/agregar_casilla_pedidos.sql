-- ============================================================================
-- CASILLA DE PEDIDOS (etapa 3, tramo 1: registro de mails y configuración)
-- ============================================================================
-- El sistema lee la casilla de mail de la empresa (Gmail vivo, con años de
-- correos) en modo SOLO LECTURA ESTRICTA: nunca borra, nunca mueve, nunca
-- marca como leído, nunca responde. Solo mira correos posteriores a la
-- fecha de activación y solo de remitentes permitidos.
--
-- La CLAVE de la casilla NO está acá: va en la variable de Railway
-- CLAVE_CASILLA_PEDIDOS (una por servicio). Si estuviera en la base,
-- cualquiera que entre al editor SQL tendría acceso al correo de la empresa.
--
-- casillas_pedidos es una tabla de N filas aunque hoy haya una sola:
-- cada fila = una casilla + UN cliente + sus remitentes permitidos. Si
-- mañana Coto o Taylem mandan su pedido al mismo buzón, es un INSERT
-- (misma direccion, otro cliente, otros remitentes) — no un ALTER.
--
-- ADITIVO PURO: no modifica ninguna tabla existente. Correr en las DOS
-- bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

create table casillas_pedidos (
    id                    bigint generated always as identity primary key,
    -- La dirección del buzón (también es el usuario IMAP). El servidor
    -- queda configurable por si alguna casilla futura no es Gmail.
    direccion             text not null,
    servidor_imap         text not null default 'imap.gmail.com',
    -- El cliente cuyos pedidos llegan por esta casilla/remitentes.
    cliente_id            bigint not null references clientes (id),
    -- Direcciones de remitente permitidas, separadas por coma. Filtro
    -- crítico: lo que no venga de acá NI SE DESCARGA del buzón.
    remitentes_permitidos text not null,
    activa                boolean not null default false,
    -- Solo se miran correos posteriores a esto. Se fija al activar y es
    -- editable a mano desde Sistema (p. ej. para releer un día puntual).
    fecha_activacion      timestamptz,
    -- Tramo 2: confirmar solo el pedido que cuadra 100% y no reemplaza a
    -- ninguno. En tramo 1 el toggle existe pero todo queda pendiente.
    auto_confirmar        boolean not null default false,
    -- Estado de la revisión, para que una falla se VEA y no pase en
    -- silencio: última revisión exitosa por un lado, último error por el
    -- otro (si el error es más nuevo que la última exitosa, algo anda mal).
    ultima_revision_el    timestamptz,
    ultimo_error          text,
    ultimo_error_el       timestamptz,
    creado_en             timestamptz not null default now(),
    unique (direccion, cliente_id)
);

comment on table casillas_pedidos is
    'Configuración de lectura de la casilla de pedidos: una fila por casilla+cliente con sus remitentes permitidos (hoy una sola: Dia). Solo lectura estricta del buzón; la clave IMAP vive en la variable de Railway CLAVE_CASILLA_PEDIDOS, jamás acá.';

-- Cada mail de pedido detectado queda registrado UNA sola vez (unique por
-- Message-ID: la idempotencia de toda la etapa 3). El cuerpo crudo
-- completo se guarda SIEMPRE, como respaldo de qué llegó exactamente.
create table mails_pedido (
    id            bigint generated always as identity primary key,
    casilla_id    bigint not null references casillas_pedidos (id),
    cliente_id    bigint not null references clientes (id),
    message_id    text not null unique,
    remitente     text not null,
    asunto        text,
    -- La fecha del encabezado Date del mail (cuándo lo mandó Dia).
    recibido_el   timestamptz not null,
    -- El cuerpo tal cual llegó (HTML o texto plano), SIN limpiar: el
    -- respaldo último para auditar qué leyó la IA contra qué llegó.
    cuerpo_crudo  text not null,
    -- El cuerpo pasado a texto (tablas HTML -> filas con celdas separadas
    -- por tabulador, celdas vacías conservadas). Esto es lo que lee la IA.
    cuerpo_texto  text,
    estado        text not null default 'pendiente'
                  check (estado in ('pendiente', 'confirmado', 'ignorado', 'error')),
    -- Por qué quedó ignorado, o el detalle del error.
    motivo        text,
    -- El pedido que salió de este mail (al confirmarse el borrador).
    pedido_id     bigint references pedidos (id),
    procesado_el  timestamptz,
    creado_en     timestamptz not null default now()
);

comment on table mails_pedido is
    'Un registro por mail detectado en la casilla de pedidos (unique por Message-ID: cada mail se procesa UNA vez aunque la revisión corra mil veces). El cuerpo crudo completo se guarda siempre. pendiente = borrador por confirmar desde la revisión.';

-- Parcial para la pantalla y la futura alerta "mails de pedido sin confirmar".
create index mails_pedido_pendientes_idx
    on mails_pedido (creado_en) where estado = 'pendiente';
create index mails_pedido_casilla_idx on mails_pedido (casilla_id);

-- Verificación: las dos tablas creadas.
-- select table_name from information_schema.tables
-- where table_name in ('casillas_pedidos', 'mails_pedido');
