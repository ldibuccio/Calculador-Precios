-- ============================================================================
-- Calculador de Precios — Esquema completo consolidado (para una BASE NUEVA)
--
-- Crea de cero, en una base VACÍA, el estado FINAL de las 13 tablas que el
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
    retiro_origen              text check (retiro_origen in ('logistica', 'deposito', 'migracion', 'ingreso_directo')),
    cantidad_cajones_retirada  numeric,
    constraint compras_tipo_retiro_check check (tipo_retiro in ('Clark', 'Carro', 'Pases')),
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

commit;
