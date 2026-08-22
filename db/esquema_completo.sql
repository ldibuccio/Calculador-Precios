-- ============================================================================
-- Calculador de Precios — Esquema completo consolidado (para una BASE NUEVA)
--
-- Crea de cero, en una base VACÍA, el estado FINAL de las tablas que el
-- código usa hoy — el mismo estado al que llegó la base de Frutamax después
-- de toda la historia de migraciones de esta carpeta. Pensado para el alta
-- de una empresa nueva (ej. Palmala): correr este único archivo reemplaza
-- correr schema.sql + todas las migraciones en orden, cosa que NO funciona
-- (schema.sql crea el diseño viejo, varias migraciones son destructivas o
-- cargan datos de Frutamax).
--
-- NO correr en la base de Frutamax: sus tablas ya existen (los CREATE
-- fallarían, sin romper nada, pero no tiene sentido).
--
-- Qué NO crea, a propósito:
--   - Las tablas muertas del diseño original que el código no usa
--     (recepciones, pedidos_supermercado, precios_dia, parametros_historial,
--     aprendizaje_proveedores, resultados, conversion_articulos_cliente).
--     En Frutamax existen por historia; una base nueva no las necesita.
--   - Ningún dato: el catálogo inicial se copia desde la base de la otra
--     empresa con scripts/copiar_catalogo_empresa.py.
--   - El bucket "comandas" de Storage: eso NO es SQL — se crea a mano en
--     el proyecto nuevo de Supabase (Storage -> New bucket -> "comandas",
--     privado), igual que se hizo en Frutamax.
--
-- Los nombres de los constraints con nombre propio (compras_estado_check,
-- compras_retiro_origen_check, compras_tipo_retiro_check,
-- compras_cantidad_cargada_check) se conservan idénticos a los de la base
-- de Frutamax: las migraciones futuras los referencian por nombre (drop
-- constraint + add constraint) y tienen que funcionar igual en las dos
-- bases. Los checks inline generan solos el mismo nombre que en Frutamax
-- (tabla_columna_check), así que también quedan iguales.
--
-- Después de correr esto, verificar contra la base de Frutamax con
-- db/verificar_esquema.sql (la consulta corta en las dos bases, comparar).
-- ============================================================================

begin;

-- ----------------------------------------------------------------------------
-- 1. ARTICULOS — catálogo de productos
-- ----------------------------------------------------------------------------
create table articulos (
    id                    bigint generated always as identity primary key,
    nombre                text not null unique,
    codigo_interno        text unique,
    cubetas_por_caja      numeric,
    unidades_por_cajon    numeric,
    kg_por_cajon          numeric,
    activo                boolean not null default true,
    creado_en             timestamptz not null default now(),
    actualizado_en        timestamptz not null default now(),
    merma_porcentaje      numeric not null default 0,
    unidad_compra         text check (unidad_compra in ('kilo', 'unidad', 'cubeta')),
    contenido_referencia  numeric,
    grupo                 text
);

comment on table articulos is 'Catálogo de artículos. La logística por cliente (unidad de venta, envase, contenido) vive en fichas_logistica.';
comment on column articulos.unidad_compra is 'Unidad en la que se compra el artículo al proveedor (kilo, unidad o cubeta). Nulo hasta completarlo desde /articulos; sin esto no se puede cargar una compra nueva de ese artículo.';
comment on column articulos.contenido_referencia is 'Cuánto trae habitualmente el cajón/caja que se compra (ej. Mango: 10 unidades). Solo referencia: se puede editar en cada compra si ese día vino distinto.';
comment on column articulos.grupo is 'Clasificación del artículo (fruta, hortaliza, ...) — solo para separar listados, no afecta ningún cálculo. Sin CHECK: la lista de valores válidos vive en el código (GRUPOS_ARTICULO_VALIDOS).';
comment on column articulos.merma_porcentaje is 'Porcentaje de merma esperado del articulo (0 = sin merma).';

-- ----------------------------------------------------------------------------
-- 2. PROVEEDORES — identidad estable: codigo_puesto (ej. N07P41)
-- ----------------------------------------------------------------------------
create table proveedores (
    id              bigint generated always as identity primary key,
    nombre          text not null,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    codigo_puesto   text unique not null check (codigo_puesto ~ '^[NL][0-9]{2}P[0-9]{2}$')
);

comment on table proveedores is 'Proveedores del mercado. La identidad estable es codigo_puesto (ej. N07P41); el nombre es editable, la ultima correccion manda.';

-- ----------------------------------------------------------------------------
-- 3. CLIENTES + conceptos con historial de vigencia
-- ----------------------------------------------------------------------------
create table clientes (
    id              bigint generated always as identity primary key,
    nombre          text not null unique,
    activo          boolean not null default true,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now()
);

comment on table clientes is 'Clientes a los que se les vende (ej. supermercado Dia). Cada uno con sus propios conceptos (tasas y utilidad objetivo).';

create table clientes_parametros_historial (
    id                bigint generated always as identity primary key,
    cliente_id        bigint not null references clientes (id),
    nombre_parametro  text not null,
    valor             numeric not null,
    vigente_desde     date not null,
    creado_en         timestamptz not null default now(),
    tipo              text not null check (tipo in ('suma', 'resta', 'utilidad')),
    unique (cliente_id, nombre_parametro, vigente_desde)
);

comment on table clientes_parametros_historial is 'Conceptos que afectan el precio de cada cliente (descuento, utilidad, y cualquier otro que se cargue: flete, IVA, premios, etc.), con historial por fecha de vigencia. Cada concepto tiene una etiqueta libre (nombre_parametro) y una clasificación fija (tipo: suma/resta/utilidad).';
comment on column clientes_parametros_historial.nombre_parametro is 'Etiqueta libre del concepto (ej. descuento, utilidad_objetivo, flete, iva, fondo publicidad). Qué hace con el precio lo dice la columna tipo.';
comment on column clientes_parametros_historial.tipo is 'Qué hace el concepto con el precio: suma (se suma, plata del cliente, ej. IVA/premio), resta (se descuenta, ej. logística/flete) o utilidad (margen objetivo).';

-- ----------------------------------------------------------------------------
-- 4. ENVASES por cliente + costo con historial
-- ----------------------------------------------------------------------------
create table envases (
    id              bigint generated always as identity primary key,
    nombre          text not null unique,
    activo          boolean not null default true,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now()
);

comment on table envases is 'Catálogo único de envases, compartido entre todos los clientes: cada ficha logística elige el que corresponda. Un envase exclusivo de un cliente se distingue por el nombre (ver envases_sin_cliente.sql).';

create table envases_costo_historial (
    id              bigint generated always as identity primary key,
    envase_id       bigint not null references envases (id),
    costo           numeric not null,
    vigente_desde   date not null,
    creado_en       timestamptz not null default now(),
    unique (envase_id, vigente_desde)
);

comment on table envases_costo_historial is 'Costo de cada envase, con historial por fecha de vigencia.';

-- ----------------------------------------------------------------------------
-- 5. FICHAS_LOGISTICA — cómo trata cada cliente a cada artículo
-- ----------------------------------------------------------------------------
create table fichas_logistica (
    id                bigint generated always as identity primary key,
    articulo_id       bigint not null references articulos (id),
    cliente_id        bigint not null references clientes (id),
    unidad_venta      text not null check (unidad_venta in ('kilo', 'unidad', 'cubeta')),
    envase_id         bigint references envases (id),
    contenido_caja    numeric,
    envase_variable   boolean not null default false,
    creado_en         timestamptz not null default now(),
    actualizado_en    timestamptz not null default now(),
    nombre_cliente    text,
    codigo_cliente    text,
    unique (articulo_id, cliente_id)
);

comment on table fichas_logistica is 'Ficha de logistica por articulo y cliente: unidad de venta, que envase usa (fijo o variable), contenido solicitado, y el alias con el que ese cliente conoce al articulo (nombre_cliente/codigo_cliente).';
comment on column fichas_logistica.envase_variable is 'Si es true, el envase de la ficha es solo referencia/default: se decide por compra. Si es false, el envase es fijo.';

-- Bitácora append-only de fichas: foto completa en cada alta/edición/borrado,
-- escrita por la app en la misma transacción. Nada la lee para calcular.
create table fichas_logistica_historial (
    id              bigint generated always as identity primary key,
    ficha_id        bigint not null,  -- sin FK a propósito: la ficha puede ya no existir
    cliente_id      bigint not null references clientes (id),
    articulo_id     bigint not null references articulos (id),
    envase_id       bigint references envases (id),
    contenido_caja  numeric,
    unidad_venta    text not null,
    envase_variable boolean not null,
    nombre_cliente  text,
    codigo_cliente  text,
    evento          text not null check (evento in ('foto_inicial', 'alta', 'edicion', 'borrado')),
    registrado_en   timestamptz not null default now()
);

comment on table fichas_logistica_historial is
    'Bitácora append-only de fichas_logistica: foto completa de la ficha en cada alta/edición/borrado, escrita por la app en la misma transacción. Nada la lee para calcular: es solo consulta humana. Un cambio hecho a mano en la base NO queda registrado acá.';
comment on column fichas_logistica_historial.evento is
    'foto_inicial = seed de la migración (estado al momento de crear la bitácora); alta/edicion = estado que quedó grabado tras el evento; borrado = estado final de lo que se borró.';

create index idx_fichas_historial_cliente
    on fichas_logistica_historial (cliente_id, registrado_en);

-- ----------------------------------------------------------------------------
-- 6. GUIAS_COMPRA — una guía por proveedor por día; el id ES el número de guía
-- ----------------------------------------------------------------------------
create table guias_compra (
    id               bigint generated always as identity primary key,
    fecha_operacion  date not null,
    proveedor_id     bigint not null references proveedores (id),
    creada_el        timestamptz not null default now(),
    unique (fecha_operacion, proveedor_id)
);

comment on table guias_compra is 'Una guía por proveedor por día de operación. El id es el número de guía (ej. 105).';

create table fotos_guia (
    id         bigint generated always as identity primary key,
    guia_id    bigint not null references guias_compra (id),
    foto_ruta  text not null,
    creado_en  timestamptz not null default now(),
    unique (guia_id, foto_ruta)
);

comment on table fotos_guia is 'Fotos/archivos de una guía (comanda de un proveedor en un día), en el bucket "comandas". Una guía puede tener varias; un mismo archivo (foto_ruta) puede colgar de varias guías (el Listado consolidado comparte una foto entre proveedores). Reemplaza a compras.foto_ruta, que queda muerta hasta su DROP (ver APLICADO.md).';
comment on column fotos_guia.foto_ruta is 'Ruta del archivo en el bucket "comandas". El archivo físico se borra del Storage solo cuando NINGUNA guía lo referencia.';

create index fotos_guia_foto_ruta_idx on fotos_guia (foto_ruta);

-- ----------------------------------------------------------------------------
-- 7. COMPRAS — el corazón del sistema: carga, retiro y recepción de cada renglón
--
-- palets quedó del diseño original y el código no lo usa, pero se crea
-- igual para que las dos bases sean idénticas columna por columna (la
-- verificación de esquema compara contra Frutamax, que lo tiene).
-- ----------------------------------------------------------------------------
create table compras (
    id                         bigint generated always as identity primary key,
    fecha_operacion            date not null,
    articulo_id                bigint not null references articulos (id),
    proveedor_id               bigint not null references proveedores (id),
    importe                    numeric,
    sena                       numeric,
    tipo_retiro                text not null default 'Clark',
    palets                     numeric,
    cargado_el                 timestamptz not null default now(),
    cantidad_kilos             numeric,
    cantidad_fraccion          numeric,
    cantidad_cajones           numeric not null,
    contenido_por_cajon        numeric not null,
    estado                     text check (estado in ('pendiente', 'recepcionado', 'rechazado', 'no_ingresado')),
    cantidad_cajones_real      numeric,
    contenido_por_cajon_real   numeric,
    cantidad_kilos_real        numeric,
    cantidad_fraccion_real     numeric,
    procesada_el               timestamptz,
    guia_id                    bigint references guias_compra (id),
    guia_punto                 integer,
    foto_ruta                  text,
    estado_retiro              text check (estado_retiro in ('pendiente', 'retirado', 'cancelado')),
    retiro_procesado_el        timestamptz,
    retiro_origen              text check (retiro_origen in ('logistica', 'deposito', 'migracion', 'ingreso_directo', 'automatico_carro', 'automatico_cooperativa')),
    cantidad_cajones_retirada  numeric,
    cantidad_cajones_rechazada numeric,
    motivo_rechazo             text,
    carga_token                text,
    constraint compras_tipo_retiro_check check (tipo_retiro in ('Clark', 'Carro', 'Pases', 'Cooperativa')),
    constraint compras_cantidad_cargada_check check (cantidad_kilos is not null or cantidad_fraccion is not null)
);

comment on table compras is 'Cada renglón que carga el comprador (o Depósito por ingreso directo), con su retiro y su recepción.';
comment on column compras.importe is 'Importe de la compra. Nulo = compra sin precio todavia (se completa despues desde /compras/pendientes). El costeo debe excluir las filas con importe nulo.';
comment on column compras.estado is 'pendiente/recepcionado/rechazado/no_ingresado (recepción en Depósito). NULL en compras cargadas antes de que existiera Recepción.';
comment on column compras.estado_retiro is 'pendiente/retirado/cancelado. Retiro = sacar la mercadería del puesto en el Mercado, ANTES de llegar al depósito (no confundir con estado, que es la recepción en depósito).';
comment on column compras.retiro_origen is 'Quién/qué lo marcó: logistica (a mano, desde /logistica), deposito (automático al recepcionar/rechazar algo que sí pasó por el puesto del Mercado), migracion (backfill de compras viejas) o ingreso_directo (nació directo en el depósito, cargada desde /deposito/ingresar, nunca pasó por Logística).';
comment on column compras.guia_id is 'Guía de esta compra (proveedor+día). NULL en compras cargadas antes de este cambio.';
comment on column compras.guia_punto is 'Punto dentro de la guía (105.1, 105.2, ...). Se fija una sola vez al cargar, no se renumera si se borra otro renglón.';
comment on column compras.foto_ruta is 'Ruta de la foto de la comanda en el bucket privado "comandas" de Supabase Storage (NULL si la compra se cargó sin foto, o si la subida falló). Los renglones de una misma comanda comparten la misma ruta.';
comment on column compras.cantidad_cajones_retirada is 'Cajones que Logística anotó como efectivamente retirados del puesto (opcional). Registro aparte: nunca pisa cantidad_cajones ni cantidad_cajones_real, y no entra en ningún cálculo.';
comment on column compras.cantidad_cajones_rechazada is 'Bultos devueltos al proveedor en un rechazo parcial de Recepción. Solo registro: la cantidad aceptada ya queda en cantidad_cajones_real y es la que usa todo el costeo. No entra en ningún cálculo.';
comment on column compras.motivo_rechazo is 'Motivo del rechazo parcial (texto libre, opcional).';
comment on column compras.carga_token is 'Token único por comanda leída por foto, generado por el server al armar la pantalla de revisión. Todos los renglones de una misma comanda comparten el token: si el teléfono reintenta un guardado cuya respuesta se perdió (corte de internet), el server lo reconoce y no duplica nada. NULL en compras cargadas a mano o anteriores a este cambio.';

create index compras_carga_token_idx on compras (carga_token);
comment on column compras.contenido_por_cajon_real is 'Contenido por cajón real. Lo tipea Depósito directo (pesa/cuenta un bulto, no toda la carga).';

-- ----------------------------------------------------------------------------
-- 8. PRECIOS_VENTA_HISTORIAL — precio de venta por artículo y cliente
-- ----------------------------------------------------------------------------
create table precios_venta_historial (
    id              bigint generated always as identity primary key,
    articulo_id     bigint not null references articulos (id),
    cliente_id      bigint not null references clientes (id),
    precio          numeric not null,
    vigente_desde   date not null,
    creado_en       timestamptz not null default now(),
    foto_ruta       text,
    unique (articulo_id, cliente_id, vigente_desde)
);

comment on table precios_venta_historial is 'Precio de venta por artículo y cliente, con historial por fecha de vigencia. El vigente es la fila con vigente_desde más reciente que ya llegó.';
comment on column precios_venta_historial.foto_ruta is 'Ruta del archivo (foto/PDF/Excel) del que salió este precio, en el bucket privado "comandas" de Supabase Storage (NULL si se cargó a mano, o si la subida falló).';

create index precios_venta_historial_vigente_idx
    on precios_venta_historial (cliente_id, articulo_id, vigente_desde desc);

-- ----------------------------------------------------------------------------
-- 9. DISPONIBLES — planilla de stock por cliente (cabecera + detalle)
-- ----------------------------------------------------------------------------
create table disponibles (
    id              bigint generated always as identity primary key,
    cliente_id      bigint not null references clientes (id),
    fecha_desde     date not null,
    fecha_hasta     date not null,
    estado          text not null check (estado in ('borrador', 'generado')),
    version         integer,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    check (fecha_hasta >= fecha_desde)
);

comment on table disponibles is 'Cabecera de una planilla de Disponibles (mercadería en stock) para un cliente. borrador = se sigue editando; generado = ya se bajó el Excel, queda como historial.';

create unique index disponibles_un_borrador_por_cliente_idx
    on disponibles (cliente_id)
    where estado = 'borrador';

comment on index disponibles_un_borrador_por_cliente_idx is 'Un cliente no puede tener dos borradores de Disponibles abiertos a la vez.';

create table disponibles_detalle (
    id              bigint generated always as identity primary key,
    disponible_id   bigint not null references disponibles (id) on delete cascade,
    articulo_id     bigint references articulos (id),
    codigo          text,
    nombre          text not null,
    cantidad        numeric not null,
    orden           integer not null,
    unique (disponible_id, orden)
);

comment on table disponibles_detalle is 'Un renglón (artículo + cantidad) de un Disponible. codigo/nombre se COPIAN como texto al guardar — un Disponible viejo no cambia si la ficha del cliente cambia después.';

-- ----------------------------------------------------------------------------
-- 10. APRENDIZAJE_ARTICULOS — qué texto de comanda corresponde a qué artículo
-- ----------------------------------------------------------------------------
create table aprendizaje_articulos (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint not null references proveedores (id),
    texto_leido     text not null,
    articulo_id     bigint not null references articulos (id),
    creado_en       timestamptz not null default now(),
    unique (proveedor_id, texto_leido)
);

comment on table aprendizaje_articulos is 'Aprende qué texto de una comanda (por proveedor) corresponde a qué artículo.';

-- ----------------------------------------------------------------------------
-- 11. VACÍOS (Envases Puesto) — cajones de proveedores que entran y salen
--     del puesto del Mercado. Nada que ver con la tabla envases (esa es el
--     costo del envase facturado al cliente de distribución).
-- ----------------------------------------------------------------------------
create table proveedores_puesto (
    id                 bigint generated always as identity primary key,
    nombre             text not null,
    nombre_normalizado text not null unique,
    activo             boolean not null default true,
    creado_en          timestamptz not null default now()
);

comment on table proveedores_puesto is 'Proveedores del circuito del puesto (dueños de los cajones vacíos). NO son los proveedores de Compras (tabla proveedores): circuitos separados a propósito. Solo nombre; los carga la cajera, con unificación por nombre_normalizado.';
comment on column proveedores_puesto.nombre_normalizado is 'nombre en minúsculas, sin acentos ni espacios de más. El UNIQUE evita el mismo proveedor escrito de tres formas.';

create table tipos_envase_puesto (
    id            bigint generated always as identity primary key,
    proveedor_id  bigint not null references proveedores_puesto (id),
    nombre        text not null,
    activo        boolean not null default true,
    creado_en     timestamptz not null default now(),
    unique (proveedor_id, nombre)
);

comment on table tipos_envase_puesto is 'Tipos de cajón físico por proveedor del puesto (los carga la cajera). Un proveedor sin tipos cargados no aparece en las pantallas de Vacíos.';

create table clientes_puesto (
    id                 bigint generated always as identity primary key,
    nombre             text not null,
    nombre_normalizado text not null unique,
    activo             boolean not null default true,
    creado_en          timestamptz not null default now()
);

comment on table clientes_puesto is 'Clientes del puesto del Mercado (los que traen cajones vacíos). NO son los clientes de distribución (tabla clientes): tabla aparte a propósito.';
comment on column clientes_puesto.nombre_normalizado is 'nombre en minúsculas, sin acentos ni espacios de más (ver normalizar_texto). El UNIQUE acá evita que "Juan", "juan " y "JUAN" queden como tres clientes distintos: al guardar, un nombre que normaliza igual reusa el cliente existente.';

create table vacios_recibidos (
    id                 bigint generated always as identity primary key,
    cliente_puesto_id  bigint not null references clientes_puesto (id),
    proveedor_id       bigint not null references proveedores_puesto (id),
    tipo_envase_id     bigint not null references tipos_envase_puesto (id),
    cantidad           integer not null check (cantidad > 0),
    creado_en          timestamptz not null default now(),
    sena_pagada_el     timestamptz,
    anulado_el         timestamptz,
    sena_vale_el       timestamptz,
    sena_anulada_el    timestamptz,
    constraint vacios_recibidos_un_solo_cierre_de_sena
        check (num_nonnulls(sena_pagada_el, sena_vale_el, sena_anulada_el) <= 1)
);

comment on table vacios_recibidos is 'Entrada: un cliente trae cajones vacíos al puesto. La seña se le devuelve después (ver sena_pagada_el/sena_vale_el/sena_anulada_el).';
comment on column vacios_recibidos.sena_pagada_el is 'La seña se le pagó al cliente (fecha). Uno de los tres cierres posibles del pendiente de pago; los otros dos son sena_vale_el y sena_anulada_el. NULL en los tres = seña pendiente.';
comment on column vacios_recibidos.sena_vale_el is 'El pendiente se cerró con un vale (fecha). Por ahora es solo el dato "se cerró con vale" — sin numeración, cobro ni vencimiento.';
comment on column vacios_recibidos.sena_anulada_el is 'La seña se anuló: no se paga, decidido (fecha). NO anula el movimiento — los cajones entraron y siguen en el stock; para una entrada errónea está el Anular de Movimientos.';
comment on column vacios_recibidos.anulado_el is 'NULL = movimiento vigente. Los movimientos nunca se borran físicamente: anular deja el registro visible como corrección y el stock lo excluye.';

create table vacios_devueltos (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint not null references proveedores_puesto (id),
    tipo_envase_id  bigint not null references tipos_envase_puesto (id),
    cantidad        integer not null check (cantidad > 0),
    stock_sistema   integer not null,
    creado_en       timestamptz not null default now(),
    anulado_el      timestamptz
);

comment on table vacios_devueltos is 'Salida: el proveedor del puesto retira sus cajones con el camión.';
comment on column vacios_devueltos.stock_sistema is 'Stock del sistema (recibidos − devueltos, sin este movimiento) EN el instante de guardar. Si la devolución supera este número, esa diferencia queda registrada acá — no es solo un cartel que se cierra.';
comment on column vacios_devueltos.anulado_el is 'NULL = movimiento vigente. Igual que en vacios_recibidos: anular, nunca borrar.';

create table conteos_vacios (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint not null references proveedores_puesto (id),
    tipo_envase_id  bigint not null references tipos_envase_puesto (id),
    cantidad        integer not null check (cantidad >= 0),
    stock_sistema   integer not null,
    creado_en       timestamptz not null default now()
);

comment on table conteos_vacios is 'Conteo físico que carga el empleado SIN ver el stock del sistema (control cruzado: si lo ve, transcribe en vez de contar).';
comment on column conteos_vacios.stock_sistema is 'Stock del sistema EN el instante del conteo, guardado del lado del server (el empleado nunca lo ve). El cotejo compara contra esta foto exacta, aunque después entren movimientos.';

create table ajustes_vacios (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint not null references proveedores_puesto (id),
    tipo_envase_id  bigint not null references tipos_envase_puesto (id),
    cantidad        integer not null check (cantidad <> 0),
    motivo          text not null check (btrim(motivo) <> ''),
    stock_sistema   integer not null,
    creado_en       timestamptz not null default now(),
    anulado_el      timestamptz
);

comment on table ajustes_vacios is 'Ajustes de stock de Vacíos (cajera). Es un movimiento más, NUNCA pisa el stock: fila nueva con motivo obligatorio y la foto del sistema del momento — si se pudiera escribir un número arriba del stock sin dejar rastro, cualquier faltante se taparía con un ajuste y se acaba el control cruzado. El stock pasa a ser recibidos − devueltos + ajustes.';
comment on column ajustes_vacios.cantidad is 'Cajones del ajuste: positiva suma, negativa resta. Nunca 0.';
comment on column ajustes_vacios.motivo is 'Motivo obligatorio, escrito a mano. Sin motivo no se guarda (el CHECK lo garantiza también en la base).';
comment on column ajustes_vacios.stock_sistema is 'Stock del sistema (recibidos − devueltos + ajustes, SIN este ajuste) en el instante de guardar — misma foto que en devoluciones y conteos.';
comment on column ajustes_vacios.anulado_el is 'NULL = ajuste vigente. Igual que los demás movimientos: anular deja el registro visible, nunca se borra.';

-- ----------------------------------------------------------------------------
-- 12. ÍNDICES DE RENDIMIENTO
-- Ver db/agregar_indices_rendimiento.sql para la justificación de cada uno
-- (solo índices que responden a consultas reales y frecuentes del código).
-- ----------------------------------------------------------------------------

create index compras_fecha_proveedor_idx
    on compras (fecha_operacion, proveedor_id);
create index compras_sin_precio_idx
    on compras (fecha_operacion) where importe is null;
create index compras_pendientes_recepcion_idx
    on compras (guia_id, guia_punto) where estado = 'pendiente' and guia_id is not null;
create index compras_procesada_el_idx
    on compras (procesada_el) where procesada_el is not null;
create index compras_retiro_procesado_el_idx
    on compras (retiro_procesado_el) where retiro_procesado_el is not null;
create index compras_pendientes_retiro_idx
    on compras (tipo_retiro)
    where estado_retiro is distinct from 'retirado' and estado_retiro is distinct from 'cancelado';
create index compras_foto_ruta_idx
    on compras (foto_ruta, fecha_operacion) where foto_ruta is not null;
create index vacios_recibidos_stock_idx
    on vacios_recibidos (proveedor_id, tipo_envase_id) include (cantidad)
    where anulado_el is null;
create index vacios_devueltos_stock_idx
    on vacios_devueltos (proveedor_id, tipo_envase_id) include (cantidad)
    where anulado_el is null;
create index ajustes_vacios_stock_idx
    on ajustes_vacios (proveedor_id, tipo_envase_id) include (cantidad)
    where anulado_el is null;

-- ----------------------------------------------------------------------------
-- 13. PEDIDOS DE CLIENTES — el mail diario de Día (demanda, sin FK a compras)
-- ----------------------------------------------------------------------------
create table pedidos (
    id                     bigint generated always as identity primary key,
    cliente_id             bigint not null references clientes (id),
    fecha_operacion        date not null,
    origen                 text not null check (origen in ('texto', 'mail')),
    texto_original         text,
    recibido_el            timestamptz,
    mail_message_id        text,
    reemplaza_a_pedido_id  bigint references pedidos (id),
    creado_en              timestamptz not null default now(),
    anulado_el             timestamptz
);

comment on table pedidos is 'Cabecera del pedido diario de un cliente. Demanda pura: sin FK contra compras. Un pedido corregido es una fila nueva con reemplaza_a_pedido_id; el viejo se anula (anulado_el), nunca se pisa.';

create unique index pedidos_mail_message_id_unico
    on pedidos (mail_message_id) where mail_message_id is not null;
create index pedidos_cliente_fecha_idx on pedidos (cliente_id, fecha_operacion);

create table pedidos_sucursales (
    id                      bigint generated always as identity primary key,
    pedido_id               bigint not null references pedidos (id),
    sucursal                text not null,
    orden_compra            text,
    total_bultos_declarado  numeric,
    unique (pedido_id, sucursal)
);

comment on table pedidos_sucursales is 'Una fila por sucursal del pedido (VL/BZ/GR de Dia), con su orden de compra y el total de bultos declarado en el mail (control cruzado).';

create table pedidos_renglones (
    id                bigint generated always as identity primary key,
    pedido_id         bigint not null references pedidos (id),
    sucursal          text,
    articulo_id       bigint references articulos (id),
    texto_codigo      text,
    texto_descripcion text,
    cantidad          numeric not null default 0,
    armado_el         timestamptz,
    cantidad_armada   numeric,
    creado_en         timestamptz not null default now()
);

comment on table pedidos_renglones is 'Un renglon por articulo Y sucursal. articulo_id NULL = sin identificar, con el texto crudo conservado. armado_el: tilde de armado del deposito (= termine con este renglon); cantidad_armada: cuantos bultos se armaron realmente si fue menos que lo pedido (NULL = completo).';

create index pedidos_renglones_pedido_idx on pedidos_renglones (pedido_id);
create index pedidos_renglones_sin_identificar_idx
    on pedidos_renglones (pedido_id) where articulo_id is null;

create table fotos_pedido (
    id         bigint generated always as identity primary key,
    pedido_id  bigint not null references pedidos (id),
    foto_ruta  text not null,
    creado_en  timestamptz not null default now(),
    unique (pedido_id, foto_ruta)
);

comment on table fotos_pedido is 'Capturas del mail original del pedido, como respaldo visual.';

-- ----------------------------------------------------------------------------
-- 14. CASILLA DE PEDIDOS — lectura solo-lectura del buzón de la empresa
-- ----------------------------------------------------------------------------
create table casillas_pedidos (
    id                    bigint generated always as identity primary key,
    direccion             text not null,
    servidor_imap         text not null default 'imap.gmail.com',
    cliente_id            bigint not null references clientes (id),
    remitentes_permitidos text not null,
    activa                boolean not null default false,
    fecha_activacion      timestamptz,
    auto_confirmar        boolean not null default false,
    ultima_revision_el    timestamptz,
    ultimo_error          text,
    ultimo_error_el       timestamptz,
    creado_en             timestamptz not null default now(),
    unique (direccion, cliente_id)
);

comment on table casillas_pedidos is 'Configuración de lectura de la casilla de pedidos: una fila por casilla+cliente con sus remitentes permitidos. Solo lectura estricta del buzón; la clave IMAP vive en la variable de Railway CLAVE_CASILLA_PEDIDOS, jamás acá.';

create table mails_pedido (
    id            bigint generated always as identity primary key,
    casilla_id    bigint not null references casillas_pedidos (id),
    cliente_id    bigint not null references clientes (id),
    message_id    text not null unique,
    remitente     text not null,
    asunto        text,
    recibido_el   timestamptz not null,
    cuerpo_crudo  text not null,
    cuerpo_texto  text,
    estado        text not null default 'pendiente'
                  check (estado in ('pendiente', 'confirmado', 'ignorado', 'error')),
    motivo        text,
    pedido_id     bigint references pedidos (id),
    procesado_el  timestamptz,
    creado_en     timestamptz not null default now()
);

comment on table mails_pedido is 'Un registro por mail detectado en la casilla de pedidos (unique por Message-ID: cada mail se procesa UNA vez). El cuerpo crudo completo se guarda siempre. pendiente = borrador por confirmar desde la revisión.';

create index mails_pedido_pendientes_idx
    on mails_pedido (creado_en) where estado = 'pendiente';
create index mails_pedido_casilla_idx on mails_pedido (casilla_id);

commit;
