-- ============================================================================
-- Calculador de Precios — Esquema de base de datos (PostgreSQL / Supabase)
--
-- Este archivo crea la estructura de las 9 tablas acordadas en
-- docs/diseno_base_datos.md. NO carga datos, solo la estructura.
--
-- Pensado para correrlo a mano en el editor SQL de Supabase, en este orden
-- (respeta las dependencias entre tablas por las claves foráneas).
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. ARTICULOS
-- Catálogo de productos: cómo se compra y se fracciona cada uno (la ficha de
-- logística). Editable desde la app; reemplaza a las fichas fijas del código.
-- ----------------------------------------------------------------------------
create table articulos (
    id                  bigint generated always as identity primary key,
    nombre              text not null unique,
    codigo_interno      text unique, -- código propio del artículo, para no confundirlo aunque cambie el nombre
    tipo_envase         text not null check (tipo_envase in ('perdido', 'caja_chica', 'caja_grande')),
    unidad_venta        text not null check (unidad_venta in ('kilo', 'unidad', 'cubeta')),
    contenido_caja      numeric, -- cuánto trae la caja para este artículo (vacío si es envase perdido)
    cubetas_por_caja    numeric, -- solo si unidad_venta = 'cubeta'
    unidades_por_cajon  numeric, -- solo para artículos que se venden por unidad pero se pesan por palet (ej. Mango, Palta)
    kg_por_cajon        numeric, -- idem, peso del cajón del productor para calcular palets
    activo              boolean not null default true,
    creado_en           timestamptz not null default now(),
    actualizado_en      timestamptz not null default now()
);

comment on table articulos is 'Catálogo de artículos: cómo se compra y fracciona cada producto.';


-- ----------------------------------------------------------------------------
-- 2. PROVEEDORES
-- La llave real de un proveedor es nave + puesto. El nombre es editable y la
-- última corrección pisa la anterior, sin guardar historial de nombres.
-- ----------------------------------------------------------------------------
create table proveedores (
    id              bigint generated always as identity primary key,
    nave            text not null,
    puesto          text not null,
    nombre          text not null,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    unique (nave, puesto)
);

comment on table proveedores is 'Proveedores del mercado. La identidad estable es nave + puesto; el nombre es editable.';


-- ----------------------------------------------------------------------------
-- 3. COMPRAS
-- Cada renglón que carga el comprador. Se agrupan por fecha_operacion; varias
-- compras del mismo día/artículo/proveedor son las que el motor de costeo
-- promedia ponderando por cantidad.
-- ----------------------------------------------------------------------------
create table compras (
    id                bigint generated always as identity primary key,
    fecha_operacion   date not null,
    articulo_id       bigint not null references articulos (id),
    proveedor_id      bigint not null references proveedores (id),
    cantidad          numeric not null,
    unidad            text not null check (unidad in ('kilo', 'unidad')),
    importe           numeric not null,
    sena              numeric, -- opcional, por artículo (no por toda la compra)
    tipo_retiro       text not null default 'Clark' check (tipo_retiro in ('Clark', 'Carro', 'Pases')),
    palets            numeric,
    cargado_el        timestamptz not null default now()
);

comment on table compras is 'Operaciones de compra cargadas por el comprador, agrupadas por fecha de operación.';


-- ----------------------------------------------------------------------------
-- 4. RECEPCION
-- Lo que realmente entra al depósito; puede diferir de la compra en cantidad
-- y kilaje. Nunca queda cerrada de forma definitiva: el OK de Administración
-- no impide corregirla después.
-- ----------------------------------------------------------------------------
create table recepciones (
    id                              bigint generated always as identity primary key,
    fecha_operacion                 date not null,
    compra_id                       bigint references compras (id), -- vacío si es un agregado fuera de horario sin compra cargada
    articulo_id                     bigint not null references articulos (id),
    proveedor_id                    bigint references proveedores (id),
    cantidad_recibida               numeric not null,
    kilaje_recibido                 numeric,
    es_agregado_fuera_de_horario    boolean not null default false,
    aprobado_por_administracion     boolean not null default false, -- no bloquea la edición, solo indica que fue revisada
    actualizado_el                  timestamptz not null default now()
);

comment on table recepciones is 'Lo que efectivamente entra al depósito. Nunca queda cerrada de forma definitiva.';


-- ----------------------------------------------------------------------------
-- 5. PEDIDOS_SUPERMERCADO
-- Llega por mail al mediodía, dividido en tres depósitos (VL/BZ/GR). Se
-- guarda el desglose por sucursal (no solo el total) para poder hacer
-- estadísticas futuras por depósito y artículo (ej. rechazos de calidad).
-- ----------------------------------------------------------------------------
create table pedidos_supermercado (
    id                bigint generated always as identity primary key,
    fecha_operacion   date not null,
    sucursal          text not null check (sucursal in ('VL', 'BZ', 'GR')),
    articulo_id       bigint not null references articulos (id),
    cantidad          numeric not null, -- ya sumada dentro de esa sucursal si el mail repite el artículo
    recibido_el       timestamptz not null default now(),
    unique (fecha_operacion, sucursal, articulo_id)
);

comment on table pedidos_supermercado is 'Pedido diario del supermercado, desglosado por depósito (VL/BZ/GR) y artículo.';


-- ----------------------------------------------------------------------------
-- 6. PRECIOS_DIA
-- Precios negociados con el supermercado: uno por artículo por día, sin
-- distinción de sucursal (el mismo precio aplica a los tres depósitos).
-- ----------------------------------------------------------------------------
create table precios_dia (
    id                bigint generated always as identity primary key,
    fecha_operacion   date not null,
    articulo_id       bigint not null references articulos (id),
    precio            numeric not null,
    unique (fecha_operacion, articulo_id)
);

comment on table precios_dia is 'Precio negociado con el supermercado por artículo y día.';


-- ----------------------------------------------------------------------------
-- 7a. APRENDIZAJE_ARTICULOS
-- Qué texto escrito en la comanda de tal proveedor corresponde a tal
-- artículo. Complementa las reglas fijas del prompt de lector_comandas.py.
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
-- 7b. APRENDIZAJE_PROVEEDORES
-- Qué texto/membrete de la comanda corresponde a qué proveedor real.
-- ----------------------------------------------------------------------------
create table aprendizaje_proveedores (
    id              bigint generated always as identity primary key,
    texto_leido     text not null unique,
    proveedor_id    bigint not null references proveedores (id),
    creado_en       timestamptz not null default now()
);

comment on table aprendizaje_proveedores is 'Aprende qué texto de una comanda corresponde a qué proveedor.';


-- ----------------------------------------------------------------------------
-- 8. PARAMETROS_HISTORIAL
-- Parámetros del negocio (descuento, utilidad, costos de envase, kg por
-- palet), editables y con historial: un cambio de hoy no mueve los
-- resultados de días pasados, que siguen usando el valor vigente en su
-- momento.
-- ----------------------------------------------------------------------------
create table parametros_historial (
    id                  bigint generated always as identity primary key,
    nombre_parametro    text not null, -- ej. 'descuento_estandar', 'utilidad_estandar', 'costo_envase_chico'
    valor               numeric not null,
    vigente_desde       date not null, -- fecha a partir de la cual rige este valor
    creado_en           timestamptz not null default now(),
    unique (nombre_parametro, vigente_desde)
);

comment on table parametros_historial is 'Parámetros del negocio con historial de cambios por fecha de vigencia.';


-- ----------------------------------------------------------------------------
-- 9. RESULTADOS
-- Salida calculada del motor de costeo por día y artículo (no se carga a
-- mano). Se recalcula cuando llega algo tarde (recepción, precio o pedido
-- corregido).
-- ----------------------------------------------------------------------------
create table resultados (
    id                  bigint generated always as identity primary key,
    fecha_operacion     date not null,
    articulo_id         bigint not null references articulos (id),
    costo_ponderado     numeric,
    precio_sugerido     numeric,
    utilidad_real       numeric,
    cantidad_cajas      numeric,
    palets              numeric,
    recalculado_el      timestamptz not null default now(),
    unique (fecha_operacion, articulo_id)
);

comment on table resultados is 'Resultado calculado por día y artículo (costo ponderado, precio sugerido, utilidad real).';
