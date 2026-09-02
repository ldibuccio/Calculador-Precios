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
--   - Ningún dato de ninguna empresa: el catálogo inicial se copia desde
--     la base de la otra con scripts/copiar_catalogo_empresa.py. La ÚNICA
--     excepción es el plan de cuentas de Costos Fijos (sección 18): es un
--     esqueleto genérico, sin un solo importe, y sin él esa pantalla
--     arranca vacía y no se puede cargar nada.
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
-- Ojo: esa consulta mira 13 tablas, no todas — las de las secciones 13 a 18
-- (pedidos, casilla, stock, reprocesos, costos fijos) quedan afuera.
--
-- ----------------------------------------------------------------------------
-- MANTENIMIENTO — esto es lo que se olvida y hace que el archivo se pudra
-- ----------------------------------------------------------------------------
-- Este archivo tiene que reflejar SIEMPRE el estado final de Frutamax. Cada
-- vez que se agrega una migración a db/ y se corre en las dos bases, hay que
-- reflejarla acá EN EL MISMO COMMIT que la marca de APLICADO.md. Si no, una
-- empresa nueva arranca con el esquema viejo y roto — que es exactamente lo
-- que pasó entre el 2026-08-19 y el 2026-08-26, cuando quedaron afuera seis
-- subsistemas enteros.
--
-- Cómo se comprueba, sin tocar ninguna base real (así se saldó aquella
-- deuda): en un Postgres local, crear una base con este archivo y otra con
-- este archivo + las migraciones que falten, y comparar los dos pg_dump -s.
-- Tienen que salir idénticos.
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
    codigo_cliente    text
);

comment on table fichas_logistica is 'Ficha de logistica por articulo y cliente: unidad de venta, que envase usa (fijo o variable), contenido solicitado, y el alias con el que ese cliente conoce al articulo (nombre_cliente/codigo_cliente).';
comment on column fichas_logistica.envase_variable is 'Si es true, el envase de la ficha es solo referencia/default: se decide por compra. Si es false, el envase es fijo.';

-- Un cliente PUEDE tener varias fichas del mismo artículo: Banana Bolivia y
-- Banana Ecuador salen del mismo stock de Banana, con nombre, kilaje, envase
-- y precio propios. Por eso acá no hay unique (articulo_id, cliente_id) —
-- lo hubo hasta permitir_varias_fichas_por_articulo.sql. El índice va con el
-- cliente primero: sirve igual para "la ficha de este cliente para este
-- artículo" y para "todas las fichas de este cliente", que es lo más pedido.
create index fichas_logistica_cliente_articulo_idx
    on fichas_logistica (cliente_id, articulo_id);

-- La contracara de sacar esa pared: con varias fichas por artículo, el código
-- del cliente es LO que decide a qué ficha va cada renglón del pedido.
-- Normalizado (lower + trim) porque el matcheo también normaliza. Las fichas
-- sin código quedan afuera: no tener código es normal (se matchea por nombre).
create unique index fichas_logistica_codigo_cliente_unico
    on fichas_logistica (cliente_id, lower(trim(codigo_cliente)))
    where codigo_cliente is not null and trim(codigo_cliente) <> '';

comment on index fichas_logistica_codigo_cliente_unico is
    'Dos fichas del mismo cliente no pueden compartir el código: desde que un cliente puede tener varias fichas del mismo artículo, el código es lo que decide a cuál de ellas va el renglón del pedido. Repetido, el sistema elegiría una en silencio.';

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

comment on table fotos_guia is 'Fotos/archivos de una guía (comanda de un proveedor en un día), en el bucket "comandas". Una guía puede tener varias; un mismo archivo (foto_ruta) puede colgar de varias guías (el Listado consolidado comparte una foto entre proveedores). Reemplaza a la vieja compras.foto_ruta (borrada en drop_foto_ruta_compras.sql).';
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
    ficha_id        bigint references fichas_logistica (id) on delete set null,
    constraint precios_venta_historial_ficha_vigente_key unique (ficha_id, vigente_desde)
);

comment on table precios_venta_historial is 'Precio de venta por artículo y cliente, con historial por fecha de vigencia. El vigente es la fila con vigente_desde más reciente que ya llegó.';
comment on column precios_venta_historial.foto_ruta is 'Ruta del archivo (foto/PDF/Excel) del que salió este precio, en el bucket privado "comandas" de Supabase Storage (NULL si se cargó a mano, o si la subida falló).';
comment on column precios_venta_historial.ficha_id is 'La ficha a la que pertenece este precio: la clave de VENTA. Dos fichas del mismo artículo y cliente (Banana Bolivia y Banana Ecuador) tienen precios distintos porque son fichas distintas. NULL = precio huérfano (su ficha se borró o cambió de artículo): queda de historia y no se lee.';

-- La clave de venta es la FICHA, no el artículo. articulo_id se queda igual:
-- lo usa el chequeo de Disponibles ("¿este artículo tiene precio cargado?") y
-- es la referencia histórica de a qué artículo apuntaba el precio.
-- ON DELETE SET NULL a propósito: borrar una ficha (o cambiarle el artículo,
-- que la borra y crea otra) deja el precio huérfano, con su historia intacta.
create index precios_venta_historial_ficha_vigente_idx
    on precios_venta_historial (cliente_id, ficha_id, vigente_desde desc);

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

create table senas_valor_historial (
    id              bigint generated always as identity primary key,
    tipo_envase_id  bigint not null references tipos_envase_puesto (id),
    monto           numeric not null check (monto >= 0),
    vigente_desde   date not null,
    creado_en       timestamptz not null default now()
);

-- SIN unique por (tipo_envase_id, vigente_desde), a diferencia de
-- envases_costo_historial: acá una misma fecha puede tener varias filas.
-- Es lo que permite corregir un tipeo del mismo día sin perder el número
-- anterior. Gana la de creado_en más alto; este índice sirve ese orden.
create index senas_valor_historial_vigente_idx
    on senas_valor_historial (tipo_envase_id, vigente_desde desc, creado_en desc);

comment on table senas_valor_historial is 'Valor de la seña de cada tipo de envase del puesto, con historial por fecha de vigencia. Append-only de verdad: nada se borra ni se pisa. Cargar de nuevo una fecha ya cargada agrega otra fila; gana la de creado_en más alto y la anterior queda visible en el historial. Un tipo sin filas no vale 0: no tiene valor cargado.';
comment on column senas_valor_historial.monto is 'Cuánto se le seña al cliente por CADA cajón de este tipo. El total de una recepción es monto * cantidad. Cero explícito es un dato: "este envase no lleva seña", distinto de no tener fila.';
comment on column senas_valor_historial.vigente_desde is 'Desde qué día rige este monto. Se resuelve por (vigente_desde DESC, creado_en DESC) contra la fecha de la RECEPCIÓN (vacios_recibidos.creado_en::date), no la fecha del pago: la fila de mayor vigencia que no pase de ese día y, entre las de esa misma fecha, la última cargada.';

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
comment on column vacios_recibidos.sena_vale_el is 'El pendiente se cerró con un vale (fecha). Por ahora es solo el dato "se hizo vale" — sin numeración, cobro ni vencimiento.';
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
    anulado_el             timestamptz,
    armado_cerrado_el      timestamptz
);

comment on table pedidos is 'Cabecera del pedido diario de un cliente. Demanda pura: sin FK contra compras. Un pedido corregido es una fila nueva con reemplaza_a_pedido_id; el viejo se anula (anulado_el), nunca se pisa.';
comment on column pedidos.armado_cerrado_el is 'Cierre explícito del armado ("Terminar pedido"). NULL = abierto; se puede reabrir.';

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
    creado_en         timestamptz not null default now(),
    kilos_enviados    numeric,
    anulado_el        timestamptz,
    ficha_id          bigint references fichas_logistica (id) on delete set null,
    -- Sin artículo no hay ficha: un renglón sin identificar no puede traer
    -- una ficha colgada (y al revés sí: identificado sin ficha es posible).
    constraint pedidos_renglones_ficha_solo_identificados
        check (articulo_id is not null or ficha_id is null)
);

comment on table pedidos_renglones is 'Un renglon por articulo Y sucursal. articulo_id NULL = sin identificar, con el texto crudo conservado. armado_el: tilde de armado del deposito (= termine con este renglon); cantidad_armada: cuantos bultos se armaron realmente si fue menos que lo pedido (NULL = completo).';

comment on column pedidos_renglones.kilos_enviados is 'Kilos REALES con los que el depósito mandó el renglón (se cargan al tildar; editables). NULL = sin armar. Es el número que se factura.';
comment on column pedidos_renglones.anulado_el is 'Renglón que no se va a armar: anulado (baja lógica), fuera del progreso, nunca borrado.';
comment on column pedidos_renglones.ficha_id is 'La ficha con la que el cliente pidió este renglón: la clave de VENTA (precio, kilaje, envase y el nombre que ve el que arma). Sale del código del cliente al matchear. articulo_id sigue al lado como clave de COMPRA — es lo que descuenta stock, y dos fichas del mismo artículo descuentan del mismo stock. NULL = renglón sin identificar, o ficha borrada después.';

create index pedidos_renglones_pedido_idx on pedidos_renglones (pedido_id);
create index pedidos_renglones_sin_identificar_idx
    on pedidos_renglones (pedido_id) where articulo_id is null;
create index pedidos_renglones_ficha_idx
    on pedidos_renglones (ficha_id) where ficha_id is not null;

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
    asunto_filtro         text,
    remitentes_permitidos text,
    activa                boolean not null default false,
    fecha_activacion      timestamptz,
    auto_confirmar        boolean not null default false,
    ultima_revision_el    timestamptz,
    ultimo_error          text,
    ultimo_error_el       timestamptz,
    creado_en             timestamptz not null default now(),
    revision_desde        time not null default '12:00',
    revision_hasta        time not null default '15:00',
    revision_cada_minutos integer not null default 15
                          constraint casillas_revision_cada_minutos_check
                          check (revision_cada_minutos between 5 and 240),
    ultima_revision_automatica_el timestamptz,
    unique (direccion, cliente_id)
);

comment on table casillas_pedidos is 'Configuración de lectura de la casilla de pedidos: una fila por casilla+cliente con sus remitentes permitidos. Solo lectura estricta del buzón; la clave IMAP vive en la variable de Railway CLAVE_CASILLA_PEDIDOS, jamás acá.';
comment on column casillas_pedidos.revision_desde is 'Hora argentina desde la que la revisión automática chequea el buzón cada día.';
comment on column casillas_pedidos.revision_hasta is 'Hora argentina de cierre de la ventana de revisión automática (no inclusive).';
comment on column casillas_pedidos.revision_cada_minutos is 'Cada cuántos minutos se chequea el buzón dentro de la ventana (5 a 240).';
comment on column casillas_pedidos.ultima_revision_automatica_el is 'Última revisión EXITOSA hecha por el tick automático (el botón manual no la toca). La alerta de Auditoría mira SOLO esta: un tick muerto se detecta aunque el dueño revise a mano todos los días.';

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
    leido_con_ia  boolean not null default false,
    creado_en     timestamptz not null default now()
);

comment on table mails_pedido is 'Un registro por mail detectado en la casilla de pedidos (unique por Message-ID: cada mail se procesa UNA vez). El cuerpo crudo completo se guarda siempre. pendiente = borrador por confirmar desde la revisión.';

create index mails_pedido_pendientes_idx
    on mails_pedido (creado_en) where estado = 'pendiente';
create index mails_pedido_casilla_idx on mails_pedido (casilla_id);

-- El latido del bucle de revisión automática. Una sola fila, id = 1.
create table revision_tick (
    id              integer primary key check (id = 1),
    ultimo_tick_el  timestamptz not null
);

comment on table revision_tick is
    'El latido del bucle de revisión automática (una sola fila, id = 1): se actualiza en cada tick, aunque no toque revisar nada. Si quedó viejo, el bucle no está corriendo — visible en Sistema sin deducir nada de logs.';

create table corte_modelo (
    id integer primary key check (id = 1),
    fecha date not null,
    creado_en timestamptz not null default now()
);

-- La fila va acá y no en el seed: sin ella el modelo nuevo no sabe desde
-- cuándo rige, y una base recién creada quedaría a medio configurar sin
-- que nada avise.
insert into corte_modelo (id, fecha) values (1, '2026-08-31');

comment on table corte_modelo is
    'La fecha de corte del modelo nuevo (una sola fila, id = 1). A partir de ella rige el FIFO nuevo y la rentabilidad real; lo anterior queda visible pero fuera de alcance, porque se cargó con reglas que dejaban salir pedidos contra cualquier mercadería. Vive en la base y no en el código para que se lea de un solo lugar.';

-- ----------------------------------------------------------------------------
-- 15. CONDICIONES DE PEDIDO — qué días se espera pedido de cada cliente
-- ----------------------------------------------------------------------------
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

-- ----------------------------------------------------------------------------
-- 16. STOCK DE DEPÓSITO — lo que no sale de compras ni de pedidos
-- ----------------------------------------------------------------------------
-- El stock por artículo NUNCA se guarda: se calcula siempre (compras
-- recepcionadas + estos movimientos − renglones armados − reprocesos).
create table movimientos_stock (
    id bigint generated always as identity primary key,
    articulo_id bigint not null references articulos (id),
    tipo text not null check (tipo in ('ajuste', 'merma', 'reingreso_rechazo', 'stock_inicial',
                                       'cierre_modelo_viejo')),
    cantidad numeric not null check (cantidad <> 0),
    motivo text not null check (btrim(motivo) <> ''),
    cliente_id bigint references clientes (id),
    fecha_operacion date not null,
    stock_sistema numeric not null,
    creado_en timestamptz not null default now(),
    anulado_el timestamptz,
    -- Reingreso por rechazo: de qué renglón armado volvió y a qué costo.
    pedido_renglon_id bigint references pedidos_renglones (id),
    costo_por_bulto numeric check (costo_por_bulto is null or costo_por_bulto >= 0),
    -- Reingreso por rechazo: qué se hizo con lo que volvió.
    destino_rechazo text
        check (destino_rechazo is null or destino_rechazo in ('stock', 'segunda', 'reproceso')),
    bultos_segunda numeric check (bultos_segunda is null or bultos_segunda > 0),
    -- Merma dirigida a un lote puntual (NULL = FIFO, el default).
    lote_tipo text
        check (lote_tipo is null
               or lote_tipo in ('guia', 'reproceso', 'reingreso_rechazo', 'ajuste', 'stock_inicial')),
    lote_origen_id bigint,
    constraint movimientos_stock_merma_negativa
        check (tipo <> 'merma' or cantidad < 0),
    constraint movimientos_stock_reingreso_positivo
        check (tipo <> 'reingreso_rechazo' or cantidad > 0),
    constraint movimientos_stock_cliente_solo_reingreso
        check (tipo = 'reingreso_rechazo' or cliente_id is null),
    -- El stock inicial del corte también lleva costo (se carga a mano): sin
    -- eso, el FIFO nuevo arrancaría costeando contra lotes sin precio.
    -- pedido_renglon_id sigue siendo exclusivo del reingreso: apunta a un
    -- renglón que volvió, y el stock inicial no vuelve de ningún lado.
    constraint movimientos_stock_vinculo_solo_reingreso
        check (
            (tipo = 'reingreso_rechazo' or pedido_renglon_id is null)
            and (tipo in ('reingreso_rechazo', 'stock_inicial') or costo_por_bulto is null)
        ),
    constraint movimientos_stock_destino_solo_reingreso
        check (tipo = 'reingreso_rechazo' or (destino_rechazo is null and bultos_segunda is null)),
    constraint movimientos_stock_segunda_segun_destino
        check (
            case
                when destino_rechazo in ('segunda', 'reproceso')
                    then bultos_segunda is not null
                else bultos_segunda is null
            end
        ),
    constraint movimientos_stock_lote_dirigido_solo_merma
        check (tipo = 'merma' or (lote_tipo is null and lote_origen_id is null)),
    constraint movimientos_stock_lote_dirigido_completo
        check ((lote_tipo is null) = (lote_origen_id is null))
);

comment on table movimientos_stock is
    'Movimientos de stock del depósito que no salen de otra tabla: ajustes (incluido el stock inicial), mermas y reingresos por rechazo del cliente. En BULTOS. Nunca pisan el stock: el stock por artículo se calcula siempre (compras recepcionadas + estos movimientos − renglones armados).';
comment on column movimientos_stock.tipo is
    'ajuste (corrección de registro), merma (siempre negativa), reingreso_rechazo (siempre positivo, lo que volvió del cliente), stock_inicial (los bultos que había en el piso el día del corte, con costo), cierre_modelo_viejo (el compensatorio por artículo que cancela el saldo del modelo anterior al corte: signo libre, sin costo, y fuera de mermas y rentabilidad por su tipo).';
comment on column movimientos_stock.cantidad is
    'Bultos, con signo: ajuste ±, merma siempre negativa, reingreso siempre positivo.';
comment on column movimientos_stock.fecha_operacion is
    'Fecha REAL del hecho (puede no ser la de carga): ordena el FIFO y el cotejo.';
comment on column movimientos_stock.stock_sistema is
    'Foto del stock del sistema del artículo al momento de cargar el movimiento, SIN este movimiento. Rastro para el control cruzado.';
comment on column movimientos_stock.cliente_id is
    'Solo para reingreso_rechazo: qué cliente devolvió la mercadería.';
comment on column movimientos_stock.pedido_renglon_id is
    'Solo reingreso_rechazo: el renglón ARMADO del pedido de origen que el cliente devolvió. Da la trazabilidad, el tope (armado − ya devuelto) y la línea "− devoluciones" de la Rentabilidad Real. NULL en reingresos viejos = sin vínculo (corregir = anular y recargar).';
comment on column movimientos_stock.costo_por_bulto is
    'Solo reingreso_rechazo: costo por bulto CONGELADO por el server al cargar, del listado anclado a la fecha del pedido de origen. NULL = no había costo a esa fecha (el lote sigue como reingreso sin costo).';
comment on column movimientos_stock.destino_rechazo is
    'Solo reingreso_rechazo: qué se hizo con lo que volvió — stock (queda para volver a mandarla, el costo no se pierde), segunda (al pool tal cual) o reproceso (vuelve a cajón grande y esos cajones van al pool). NULL en los reingresos viejos = stock. Segunda y reproceso salen del stock normal y su costo entero es pérdida ("− rechazos perdidos" en la Real).';
comment on column movimientos_stock.bultos_segunda is
    'Solo reingreso_rechazo con destino segunda/reproceso: cuántos bultos entran al pool de segunda. En segunda es la cantidad devuelta (misma caja); en reproceso son los cajones grandes que salieron (la diferencia con lo devuelto es cambio de envase, no merma).';
comment on column movimientos_stock.lote_tipo is
    'Solo merma: a qué tipo de lote se dirige (guia, reproceso, reingreso_rechazo, ajuste). NULL = FIFO como siempre, del lote más viejo — es el default de la pantalla y de todas las mermas viejas.';
comment on column movimientos_stock.lote_origen_id is
    'Solo merma: id del lote elegido en la tabla de su lote_tipo (compras, reprocesos o movimientos_stock). Polimórfico a propósito, sin FK: el lote se resuelve rejugando el FIFO. Si el lote no cubre la merma, el excedente cae a FIFO — nunca traba.';

create table conteos_stock (
    id bigint generated always as identity primary key,
    articulo_id bigint not null references articulos (id),
    cantidad numeric not null check (cantidad >= 0),
    stock_sistema numeric not null,
    creado_en timestamptz not null default now(),
    -- Sin ON DELETE SET NULL a propósito, y acá el motivo es más fuerte
    -- que en reprocesos.ficha_id: el NULL ya tiene significado propio
    -- ("los sueltos"), así que nulear al borrar una ficha convertiría un
    -- conteo de cajas en uno de sueltos, y el Cotejo mostraría una
    -- diferencia inexplicable en los dos lados a la vez.
    ficha_id bigint references fichas_logistica (id)
);

-- El orden exacto del DISTINCT ON del Cotejo, para que salga del índice
-- sin ordenar la tabla. Con el conteo partido por ficha, esta tabla pasa a
-- crecer por ficha y no por artículo.
create index conteos_stock_cotejo_idx
    on conteos_stock (articulo_id, ficha_id, creado_en desc);

comment on table conteos_stock is
    'Stock Físico del depósito: lo que el operario contó (en bultos), sin ver el sistema. stock_sistema es la foto del sistema en el instante del conteo, para el Cotejo.';
comment on column conteos_stock.ficha_id is
    'De qué ficha son las cajas que se contaron. NULL tiene dos significados que separa la fecha de corte (31/08/2026): antes del corte = conteo viejo, todo el artículo junto, no se completa; después = los BULTOS SUELTOS del artículo, un conteo válido y completo. La ficha tiene que ser del mismo artículo del conteo: eso lo controla el código, como en asignar_ficha_a_reproceso.';

-- Los tres índices del cálculo de stock: cada uno cubre una de las patas de
-- la cuenta, con INCLUDE para que salga sin tocar la tabla.
create index movimientos_stock_stock_idx
    on movimientos_stock (articulo_id) include (cantidad)
    where anulado_el is null;
create index compras_stock_deposito_idx
    on compras (articulo_id) include (cantidad_cajones_real)
    where estado = 'recepcionado';
create index pedidos_renglones_stock_idx
    on pedidos_renglones (articulo_id)
    where armado_el is not null and anulado_el is null;
create index movimientos_stock_devueltos_idx
    on movimientos_stock (pedido_renglon_id) include (cantidad)
    where pedido_renglon_id is not null and anulado_el is null;
create index movimientos_stock_rechazo_segunda_idx
    on movimientos_stock (articulo_id) include (bultos_segunda)
    where destino_rechazo in ('segunda', 'reproceso') and anulado_el is null;

-- ----------------------------------------------------------------------------
-- 17. REPROCESOS (Guías R) y SEGUNDA
-- ----------------------------------------------------------------------------
-- La lista corta del depósito, para el selector de la excepción al freno del
-- reproceso. Editable desde Administración, igual que los catálogos del
-- puesto. Se da de BAJA con activo, nunca se borra: una excepción cargada
-- apunta acá.
create table operarios_deposito (
    id        bigint generated always as identity primary key,
    nombre    text not null check (btrim(nombre) <> ''),
    activo    boolean not null default true,
    creado_en timestamptz not null default now()
);

-- El nombre NORMALIZADO es lo único: "Juan", "juan", " Juan " y "Rubén"/"ruben"
-- son la misma persona, y si entran como cuatro, contar por operario no cuenta
-- nada. Las TILDES se pliegan con translate y no con la extensión unaccent: una
-- regla de unicidad que depende de una extensión instalada es una regla que se
-- puede perder al crear la empresa siguiente.
create unique index operarios_deposito_nombre_unico
    on operarios_deposito (lower(translate(btrim(nombre), 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')));

comment on table operarios_deposito is
    'La lista corta del depósito, para el selector de la excepción al freno del reproceso. Editable desde Administración, igual que los catálogos del puesto. Se da de BAJA con activo, nunca se borra: una excepción cargada apunta acá.';
comment on column operarios_deposito.activo is
    'false = ya no aparece en el selector, pero sus excepciones viejas siguen contando. El nombre es único PLEGANDO mayúsculas, espacios de más Y TILDES: "Rubén", "ruben" y " RUBEN " son la misma persona.';

create table reprocesos (
    id bigint generated always as identity primary key,
    articulo_id bigint not null references articulos (id),
    fecha_operacion date not null,
    bultos_tomados numeric not null,
    bultos_primera numeric not null check (bultos_primera >= 0),
    bultos_segunda numeric not null check (bultos_segunda >= 0),
    bultos_merma numeric not null check (bultos_merma >= 0),
    costo_total numeric,
    costo_por_bulto_primera numeric,
    creado_en timestamptz not null default now(),
    anulado_el timestamptz,
    cliente_id bigint references clientes (id),
    -- Sin ON DELETE SET NULL a propósito (a diferencia de
    -- pedidos_renglones.ficha_id): acá el NULL significa "sin asignar", y
    -- nulear en silencio al borrar una ficha volvería un reproceso
    -- asignado indistinguible de uno sin asignar.
    ficha_id bigint references fichas_logistica (id),
    tipo text not null default 'normal' check (tipo in ('normal', 'inicial')),
    -- El operario corrigió el reparto por lote que propuso el server.
    consumos_editados boolean not null default false,
    -- La excepción al freno: por qué se cargó sin remanente, y quién.
    -- El motivo ES la marca (NULL = no hubo excepción), para que no haya un
    -- booleano que pueda contradecirlo. El quién sale de una lista y no de un
    -- campo libre: con texto libre la misma persona entra como "juan", "Juan"
    -- y "jaun", y contar por operario deja de contar nada.
    excepcion_motivo text,
    excepcion_operario_id bigint references operarios_deposito (id),
    -- El reproceso inicial PRODUCE SIN CONSUMIR: las cajas armadas que había
    -- en el piso el día del corte ya existen, y los cajones que las
    -- originaron no se van a cargar nunca. Vive en el dato (toma cero) y no
    -- en el código, porque el cálculo de stock ya resta SUM(bultos_tomados).
    constraint reprocesos_bultos_tomados_check
        check ((tipo = 'inicial' and bultos_tomados = 0)
               or (tipo = 'normal' and bultos_tomados > 0)),
    -- Los dos datos de la excepción viajan juntos y ninguno puede ir vacío.
    -- Los "is not null" NO son redundantes: en Postgres un check que evalúa a
    -- NULL se da por cumplido, y sin ellos una guía con motivo y sin quién
    -- entraba igual.
    constraint reprocesos_excepcion_completa
        check (
            (excepcion_motivo is null and excepcion_operario_id is null)
            or (excepcion_motivo is not null and excepcion_operario_id is not null
                and btrim(excepcion_motivo) <> '')
        )
);

comment on table reprocesos is
    'Guías R: transformaciones del depósito (tomo bultos del stock, armo cajas de primera + segunda + merma, mismo artículo). El id es el número de guía. El stock se deriva de acá (− tomados, + primera); la segunda es un pool aparte.';
comment on column reprocesos.costo_total is
    'Costo congelado al cargar: Σ (bultos × costo_por_bulto) de los consumos. NULL = costo incompleto (algún lote sin precio). TODO el costo va a la primera; segunda y merma valen cero. NUNCA lo lee la cotización.';
comment on column reprocesos.costo_por_bulto_primera is
    'costo_total / bultos_primera, congelado. NULL si el costo está incompleto o no hubo primera.';
comment on column reprocesos.cliente_id is
    'Para quién se armó la primera (dato de trazabilidad: el stock sigue sin dueño). NULL = guía vieja, sin cliente. La alerta de Auditoría cruza este cliente contra el de los pedidos que el FIFO atribuye a esta primera.';
comment on column reprocesos.ficha_id is
    'A qué ficha fueron las cajas de primera de esta guía R. NULL tiene dos significados que separa la fecha de corte (31/08/2026): antes del corte = dato viejo que no se completa; después = SIN ASIGNAR, y hay que completarlo. No se deriva de (articulo_id, cliente_id): un cliente puede tener varias fichas del mismo artículo, así que esa derivación es ambigua por diseño.';
comment on column reprocesos.consumos_editados is
    'El operario corrigió el reparto por lote que propuso el server. false = el reparto es el que salió del FIFO. Va por guía y no por consumo: lo que hay que poder contestar es si el reparto lo declaró una persona, no qué renglón tocó.';
comment on column reprocesos.excepcion_motivo is
    'Por qué se cargó esta guía pese al freno (no había remanente a la fecha). NULL = no hubo excepción: el motivo ES la marca, para que no haya un booleano que pueda contradecirlo.';
comment on column reprocesos.excepcion_operario_id is
    'Quién usó la excepción, elegido de operarios_deposito. Selector y no texto libre: con texto libre la misma persona entra como "juan", "Juan" y "jaun", y contar por operario deja de contar nada.';
comment on column reprocesos.tipo is
    'normal = el reproceso de todos los días: toma bultos del stock y produce primera, segunda y merma. inicial = las cajas que ya estaban armadas en el piso el día del corte (31/08/2026): PRODUCEN SIN CONSUMIR (bultos_tomados = 0), porque los cajones que las originaron nunca se cargaron. El check obliga las dos cosas.';

-- Parcial: los reprocesos sin asignar no se buscan por ficha, y el índice
-- que importa es el de "cuántas cajas hay de esta ficha".
create index reprocesos_ficha_idx
    on reprocesos (ficha_id) where ficha_id is not null;

-- Contar las excepciones al freno por operario y por día sin recorrer la
-- tabla entera. Parcial: las guías sin excepción —casi todas— no entran.
create index reprocesos_excepcion_idx
    on reprocesos (fecha_operacion, excepcion_operario_id)
    where excepcion_motivo is not null;

create table reprocesos_consumos (
    id bigint generated always as identity primary key,
    reproceso_id bigint not null references reprocesos (id),
    origen text not null check (origen in ('compra', 'ajuste', 'reingreso_rechazo', 'reproceso',
                                          'stock_inicial', 'sin_lote')),
    compra_id bigint references compras (id),
    origen_id bigint,
    bultos numeric not null check (bultos > 0),
    costo_por_bulto numeric,
    constraint reprocesos_consumos_compra_coherente
        check ((origen = 'compra') = (compra_id is not null))
);

comment on table reprocesos_consumos is
    'De qué lote salió cada bulto tomado, escrito por el server corriendo FIFO al cargar (el operario no elige lote). Documento congelado: si después se corrige una recepción, el stock vivo se reacomoda pero esta trazabilidad y su costo no se mueven.';
comment on column reprocesos_consumos.origen is
    'compra (lote de guía de compra), ajuste (ej. stock inicial), reingreso_rechazo, reproceso (primera de otra guía R), o sin_lote (se tomó más de lo que los lotes cubrían: el piso es la verdad, no se traba).';

-- El respaldo de las fichas que el corte del modelo pone en NULL.
-- Al cortar, las guías R pre-corte con ficha asignada dejan de contar POR
-- FICHA (sus cajas siguen contando en el total del artículo, que el
-- compensatorio lleva a cero). El dato viejo no se pierde: queda acá, que es a
-- la vez el registro de qué se tocó y lo único que hace posible un rollback
-- exacto. Nace vacía y solo se llena el día del corte de esa empresa.
create table corte_respaldo_fichas_reprocesos (
    reproceso_id bigint primary key references reprocesos (id),
    ficha_id     bigint not null references fichas_logistica (id),
    guardado_el  timestamptz not null default now()
);

comment on table corte_respaldo_fichas_reprocesos is
    'Qué ficha tenía cada guía R antes de que el corte del modelo se la pusiera en NULL. Una fila por guía tocada. No se borra: es el rastro de la puesta a cero.';

create table remitos_segunda (
    id bigint generated always as identity primary key,
    articulo_id bigint not null references articulos (id),
    bultos numeric not null check (bultos > 0),
    fecha_operacion date not null,
    creado_en timestamptz not null default now(),
    anulado_el timestamptz
);

comment on table remitos_segunda is
    'Segunda remitida al Puesto (destino fijo): sale del pool de segunda y deja de ser problema del depósito. El recupero económico va aparte, más adelante.';

create index reprocesos_stock_idx
    on reprocesos (articulo_id)
    include (bultos_tomados, bultos_primera, bultos_segunda)
    where anulado_el is null;
create index reprocesos_consumos_reproceso_idx
    on reprocesos_consumos (reproceso_id);
create index remitos_segunda_stock_idx
    on remitos_segunda (articulo_id) include (bultos)
    where anulado_el is null;

-- ----------------------------------------------------------------------------
-- 18. COSTOS FIJOS — plan de cuentas, fotos de importe e inflación
-- ----------------------------------------------------------------------------
create table grupos_costos_fijos (
    id bigint generated always as identity primary key,
    numero integer not null unique check (numero > 0),
    nombre text not null check (btrim(nombre) <> ''),
    creado_en timestamptz not null default now(),
    baja_el timestamptz
);

comment on table grupos_costos_fijos is
    'Plan de cuentas de Costos Fijos, nivel padre. El número lo elige el dueño (10 = Sueldos): espaciado para que entren grupos nuevos sin renumerar.';

create table subcuentas_costos_fijos (
    id bigint generated always as identity primary key,
    grupo_id bigint not null references grupos_costos_fijos (id),
    numero integer not null check (numero > 0),
    nombre text not null check (btrim(nombre) <> ''),
    creado_en timestamptz not null default now(),
    -- Primer día del MES desde el que ya no cuenta (baja lógica con mes).
    baja_desde date check (baja_desde is null or extract(day from baja_desde) = 1),
    unique (grupo_id, numero)
);

comment on table subcuentas_costos_fijos is
    'Plan de cuentas de Costos Fijos, nivel hijo (10.1 = grupo 10, subcuenta 1). Los importes viven SOLO acá; el grupo agrega. baja_desde: primer mes que ya no cuenta (baja lógica con mes, nunca DELETE).';

create table importes_costos_fijos (
    id bigint generated always as identity primary key,
    subcuenta_id bigint not null references subcuentas_costos_fijos (id),
    -- Primer día del mes de la foto: el importe vale tal cual en ese mes.
    mes_desde date not null check (extract(day from mes_desde) = 1),
    importe numeric not null check (importe >= 0),
    alcance text not null default 'en_adelante'
        check (alcance in ('en_adelante', 'solo_este_mes')),
    creado_en timestamptz not null default now(),
    anulado_el timestamptz
);

comment on table importes_costos_fijos is
    'Las FOTOS de importe de cada subcuenta. El valor de un mes se CALCULA siempre: última foto en_adelante <= mes, inflada por los índices posteriores; una foto solo_este_mes pisa únicamente su mes. Corregir = foto nueva (la serie es el historial); error = anular y recargar.';

create table indices_inflacion (
    -- Primer día del mes. El % es la inflación DE ese mes (respecto del
    -- anterior): la foto de agosto se multiplica por el % de septiembre
    -- para valer en septiembre. Puede ser negativo.
    mes date primary key check (extract(day from mes) = 1),
    porcentaje numeric not null,
    actualizado_en timestamptz not null default now()
);

comment on table indices_inflacion is
    'Índice de inflación mensual, cargado por el dueño (editable: es un parámetro, no un hecho — editar un mes pasado recalcula los meses que lo usan). Si falta el de un mes, el sistema AVISA y no calcula: jamás inventa.';

create index importes_costos_fijos_subcuenta_idx
    on importes_costos_fijos (subcuenta_id, mes_desde)
    where anulado_el is null;

-- El plan de cuentas de arranque. Es lo ÚNICO que este archivo carga como
-- dato, y va a propósito: no es historia de ninguna empresa (no lleva un
-- solo importe), es el esqueleto genérico sin el cual la pantalla de Costos
-- Fijos arranca vacía y no se puede cargar nada. Igual que en las dos bases
-- de hoy, que salieron de agregar_costos_fijos.sql. El dueño lo edita: los
-- números están espaciados justamente para eso.
insert into grupos_costos_fijos (numero, nombre) values
    (10, 'Sueldos'),
    (20, 'Cargas sociales'),
    (30, 'Impuestos'),
    (40, 'Ocupación'),
    (50, 'Servicios profesionales'),
    (60, 'Insumos y consumos'),
    (70, 'Mantenimiento y equipos'),
    (80, 'Varios');

insert into subcuentas_costos_fijos (grupo_id, numero, nombre)
select g.id, s.numero, s.nombre
from (values
    (20, 1, 'Cargas sociales'),
    (20, 2, 'Aguinaldos'),
    (20, 3, 'Sindicato'),
    (20, 4, 'Indemnizaciones'),
    (20, 5, 'Extra empleados'),
    (30, 1, 'IIBB'),
    (30, 2, 'Retenciones IIBB'),
    (30, 3, 'IVA'),
    (30, 4, 'Autónomos'),
    (30, 5, 'Moratorias'),
    (30, 6, 'Impuestos varios'),
    (40, 1, 'Canon y tasa'),
    (40, 2, 'Luz'),
    (40, 3, 'Seguridad'),
    (40, 4, 'Teléfono'),
    (40, 5, 'Internet'),
    (50, 1, 'Contador'),
    (50, 2, 'Sistemas de computación'),
    (50, 3, 'Sistema Market'),
    (50, 4, 'Seguros'),
    (60, 1, 'Limpieza'),
    (60, 2, 'Alimentos'),
    (60, 3, 'Farmacia'),
    (60, 4, 'Librería'),
    (60, 5, 'Imprenta'),
    (60, 6, 'Embalajes'),
    (60, 7, 'Ropa de trabajo'),
    (70, 1, 'Mantenimiento'),
    (70, 2, 'Clark'),
    (70, 3, 'Aserradero'),
    (70, 4, 'Muebles y frío'),
    (70, 5, 'Biodomo'),
    (80, 1, 'Representación'),
    (80, 2, 'Varios')
) as s (grupo_numero, numero, nombre)
join grupos_costos_fijos g on g.numero = s.grupo_numero;

-- ----------------------------------------------------------------------------
-- 19. ALERTAS — la foto del último cálculo de cada control
-- ----------------------------------------------------------------------------
-- Una fila por alerta, se pisa en cada corrida: no es historial. El título, la
-- URL y a qué módulos pertenece viven en el registro de app/main.py, no acá —
-- por eso agregar una alerta nueva no toca la base.
create table alertas_estado (
    codigo        text primary key,
    casos         integer not null check (casos >= 0),
    mas_viejo     date,
    calculada_el  timestamptz not null,
    duracion_ms   integer,
    error         text
);

comment on table alertas_estado is
    'Foto del último cálculo de cada alerta, una fila por código. Se pisa en cada corrida: no es historial. El título, la URL y los módulos NO están acá: viven en el registro de app/main.py, así agregar una alerta no toca la base.';
comment on column alertas_estado.calculada_el is
    'Cuándo se calculó esta alerta. Es el dato que la pantalla muestra ("hace 3 h") y a la vez el latido del cálculo automático: se escribe siempre, aunque casos sea 0.';
comment on column alertas_estado.error is
    'Si la consulta de esta alerta falló, el mensaje. La alerta queda con su valor viejo y su calculada_el vieja: se muestra vencida, no en cero.';

commit;
