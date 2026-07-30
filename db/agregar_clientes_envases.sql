-- ============================================================================
-- Calculador de Precios — Clientes, envases y fichas de logística por cliente
--
-- Antes el sistema asumía un solo cliente implícito ("Día"), con un
-- descuento, una utilidad y dos costos de envase únicos y globales. Este
-- archivo agrega soporte para varios clientes, cada uno con su propio
-- descuento, utilidad y envases.
--
-- Correr DESPUÉS de db/schema.sql y db/seed_datos_iniciales.sql, a mano en
-- el editor SQL de Supabase. NO se ejecuta acá.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. CLIENTES
-- Antes el descuento y la utilidad eran un valor único global
-- (parametros_historial). Ahora cada cliente tiene el suyo, con historial de
-- vigencia (mismo criterio que ya usamos: un cambio de hoy no mueve los días
-- pasados).
-- ----------------------------------------------------------------------------
create table clientes (
    id              bigint generated always as identity primary key,
    nombre          text not null unique,
    activo          boolean not null default true,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now()
);

comment on table clientes is 'Clientes a los que se les vende (ej. supermercado Día). Cada uno con su propio descuento y utilidad objetivo.';

create table clientes_parametros_historial (
    id                bigint generated always as identity primary key,
    cliente_id        bigint not null references clientes (id),
    nombre_parametro  text not null check (nombre_parametro in ('descuento', 'utilidad_objetivo')),
    valor             numeric not null,
    vigente_desde     date not null,
    creado_en         timestamptz not null default now(),
    unique (cliente_id, nombre_parametro, vigente_desde)
);

comment on table clientes_parametros_historial is 'Descuento y utilidad objetivo de cada cliente, con historial por fecha de vigencia.';


-- ----------------------------------------------------------------------------
-- 2. ENVASES
-- Antes el costo del envase (chico/grande) era único y global. Ahora cada
-- cliente puede tener sus propios envases, cada uno con su propio costo con
-- historial.
-- ----------------------------------------------------------------------------
create table envases (
    id              bigint generated always as identity primary key,
    cliente_id      bigint not null references clientes (id),
    nombre          text not null, -- ej. 'Caja Chica Día'
    activo          boolean not null default true,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    unique (cliente_id, nombre)
);

comment on table envases is 'Envases que usa cada cliente (ej. Caja Chica Día, Caja Grande Día), con su costo.';

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
-- 3. FICHAS_LOGISTICA
-- Qué envase usa cada artículo para cada cliente, y cuánto contenido trae la
-- caja en ese caso puntual. No se toca articulos (salvo merma_porcentaje más
-- abajo): sus columnas de envase/contenido de caja quedan como configuración
-- por defecto; esta tabla permite que varíe por cliente.
-- ----------------------------------------------------------------------------
create table fichas_logistica (
    id              bigint generated always as identity primary key,
    articulo_id     bigint not null references articulos (id),
    cliente_id      bigint not null references clientes (id),
    envase_id       bigint references envases (id), -- vacío si es envase perdido (no usa caja compartida)
    contenido_caja  numeric, -- cuánto trae la caja para este artículo + cliente (vacío si es envase perdido)
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    unique (articulo_id, cliente_id)
);

comment on table fichas_logistica is 'Ficha de logística por artículo y cliente: qué envase usa y contenido de la caja.';


-- ----------------------------------------------------------------------------
-- 4. cliente_id en precios_dia y pedidos_supermercado
-- El precio negociado y el pedido ahora pueden variar por cliente. Se
-- actualiza también la regla de "no duplicados" para que incluya el cliente.
--
-- cliente_id queda opcional (nullable) por las dudas de que ya haya filas
-- cargadas en estas tablas. Si están vacías todavía, se puede pasar a
-- "not null" después con un ALTER TABLE aparte.
-- ----------------------------------------------------------------------------
alter table precios_dia add column cliente_id bigint references clientes (id);
alter table precios_dia drop constraint if exists precios_dia_fecha_operacion_articulo_id_key;
alter table precios_dia add constraint precios_dia_fecha_cliente_articulo_key unique (fecha_operacion, cliente_id, articulo_id);

alter table pedidos_supermercado add column cliente_id bigint references clientes (id);
alter table pedidos_supermercado drop constraint if exists pedidos_supermercado_fecha_operacion_sucursal_articulo_id_key;
alter table pedidos_supermercado add constraint pedidos_supermercado_fecha_cliente_sucursal_articulo_key unique (fecha_operacion, cliente_id, sucursal, articulo_id);


-- ----------------------------------------------------------------------------
-- 5. merma_porcentaje en articulos
-- ----------------------------------------------------------------------------
alter table articulos add column merma_porcentaje numeric not null default 0;

comment on column articulos.merma_porcentaje is 'Porcentaje de merma esperado del artículo (0 = sin merma).';


-- ----------------------------------------------------------------------------
-- Nota: el costo de compra (tabla compras) sigue siendo único, sin
-- distinción de cliente. No se le agrega cliente_id.
-- ----------------------------------------------------------------------------


-- ============================================================================
-- SEED: cliente "Día" y sus envases
-- ============================================================================

insert into clientes (nombre) values ('Día');

insert into clientes_parametros_historial (cliente_id, nombre_parametro, valor, vigente_desde)
select id, 'descuento', 0.23, '2020-01-01' from clientes where nombre = 'Día'
union all
select id, 'utilidad_objetivo', 0.20, '2020-01-01' from clientes where nombre = 'Día';

insert into envases (cliente_id, nombre)
select id, 'Caja Chica Día' from clientes where nombre = 'Día'
union all
select id, 'Caja Grande Día' from clientes where nombre = 'Día';

insert into envases_costo_historial (envase_id, costo, vigente_desde)
select id, 650, '2020-01-01' from envases where nombre = 'Caja Chica Día'
union all
select id, 1600, '2020-01-01' from envases where nombre = 'Caja Grande Día';
