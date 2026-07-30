-- ============================================================================
-- Calculador de Precios — Migración final: clientes, envases y logística
--
-- Deja la base en su estado final correcto para el modelo de "varios
-- clientes". Es seguro correrlo tanto si NUNCA corriste
-- db/agregar_clientes_envases.sql, como si ya lo corriste antes: todo lo
-- que crea, primero lo borra si existía (DROP ... IF EXISTS), así no
-- importa desde qué estado partís.
--
-- La base solo tiene datos de prueba, así que se borra y recrea lo que
-- haga falta sin problema. Todo corre en una sola transacción: si algo
-- falla a mitad de camino, no queda nada a medio migrar.
--
-- Correr DESPUÉS de db/schema.sql y db/seed_datos_iniciales.sql, a mano en
-- el editor SQL de Supabase. NO se ejecuta acá.
-- ============================================================================

begin;

-- ----------------------------------------------------------------------------
-- 1. Limpiar columnas de logística "por defecto" en articulos
-- tipo_envase, contenido_caja y unidad_venta pasan a fichas_logistica (por
-- artículo + cliente): el mismo artículo puede venderse por kilo para un
-- cliente y por unidad para otro. cubetas_por_caja, unidades_por_cajon y
-- kg_por_cajon SE QUEDAN en articulos: describen cómo llega el cajón del
-- productor al depósito, antes de repartir nada a ningún cliente.
-- ----------------------------------------------------------------------------
alter table articulos drop column if exists tipo_envase;
alter table articulos drop column if exists contenido_caja;
alter table articulos drop column if exists unidad_venta;


-- ----------------------------------------------------------------------------
-- 2. Borrar los parámetros globales que ya no se usan
-- Ahora el descuento y la utilidad son por cliente, y los costos de envase
-- están en la tabla envases. kg_por_palet sigue siendo global (no depende
-- del cliente) y no se toca.
-- ----------------------------------------------------------------------------
delete from parametros_historial
where nombre_parametro in ('descuento_estandar', 'utilidad_estandar', 'costo_envase_chico', 'costo_envase_grande');


-- ----------------------------------------------------------------------------
-- 3. Recrear de cero clientes / envases / fichas_logistica
-- (por si ya existían de una corrida anterior de agregar_clientes_envases.sql)
-- ----------------------------------------------------------------------------
drop table if exists fichas_logistica cascade;
drop table if exists envases_costo_historial cascade;
drop table if exists envases cascade;
drop table if exists clientes_parametros_historial cascade;
drop table if exists clientes cascade;

alter table precios_dia drop constraint if exists precios_dia_fecha_cliente_articulo_key;
alter table precios_dia drop constraint if exists precios_dia_fecha_operacion_articulo_id_key;
alter table precios_dia drop column if exists cliente_id;

alter table pedidos_supermercado drop constraint if exists pedidos_supermercado_fecha_cliente_sucursal_articulo_key;
alter table pedidos_supermercado drop constraint if exists pedidos_supermercado_fecha_operacion_sucursal_articulo_id_key;
alter table pedidos_supermercado drop column if exists cliente_id;


-- ----------------------------------------------------------------------------
-- 3b. Compras: reemplazar cantidad/unidad por los dos datos crudos
-- Para costear el mismo artículo de varias formas (por kilo o por unidad,
-- según el cliente), se cargan los DOS datos crudos de la misma compra:
-- cuántos kilos y cuántas unidades se compraron (ej. mango: 10 unidades,
-- 4 kg). Sin factores de conversión: el sistema deriva costo por kilo
-- (importe / cantidad_kilos) y costo por unidad (importe / cantidad_unidades)
-- directamente de estos dos números.
-- ----------------------------------------------------------------------------
alter table compras drop column if exists cantidad;
alter table compras drop column if exists unidad;

alter table compras add column cantidad_kilos numeric;
alter table compras add column cantidad_unidades numeric;
alter table compras add constraint compras_cantidad_cargada_check
    check (cantidad_kilos is not null or cantidad_unidades is not null);


-- ----------------------------------------------------------------------------
-- 4. CLIENTES
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
-- 5. ENVASES
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
-- 6. FICHAS_LOGISTICA
-- Única fuente de verdad de en qué unidad se vende cada artículo para cada
-- cliente, qué envase usa, y cuánto contenido trae la caja en ese caso
-- puntual. El mismo artículo puede tener unidad_venta distinta según el
-- cliente (ej. Mango: un cliente lo compra por unidad, otro por kilo).
-- ----------------------------------------------------------------------------
create table fichas_logistica (
    id              bigint generated always as identity primary key,
    articulo_id     bigint not null references articulos (id),
    cliente_id      bigint not null references clientes (id),
    unidad_venta    text not null check (unidad_venta in ('kilo', 'unidad', 'cubeta')),
    envase_id       bigint references envases (id), -- vacío si no usa un envase compartido
    contenido_caja  numeric, -- cuánto trae la caja para este artículo + cliente (vacío si no usa envase compartido)
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    unique (articulo_id, cliente_id)
);

comment on table fichas_logistica is 'Ficha de logística por artículo y cliente: unidad de venta, qué envase usa y contenido de la caja.';


-- ----------------------------------------------------------------------------
-- 7. cliente_id en precios_dia y pedidos_supermercado
-- ----------------------------------------------------------------------------
alter table precios_dia add column cliente_id bigint references clientes (id);
alter table precios_dia add constraint precios_dia_fecha_cliente_articulo_key unique (fecha_operacion, cliente_id, articulo_id);

alter table pedidos_supermercado add column cliente_id bigint references clientes (id);
alter table pedidos_supermercado add constraint pedidos_supermercado_fecha_cliente_sucursal_articulo_key unique (fecha_operacion, cliente_id, sucursal, articulo_id);


-- ============================================================================
-- SEED: cliente "Día", sus envases, y la logística de los 29 artículos
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

-- Ficha de logística de los 29 artículos para el cliente "Día", con la
-- misma unidad de venta / envase / contenido de caja que ya tenían.
insert into fichas_logistica (articulo_id, cliente_id, unidad_venta, envase_id, contenido_caja)
select a.id, cl.id, v.unidad_venta, e.id, v.contenido_caja
from (values
    -- Sin envase compartido (envase perdido), por kilo
    ('Cereza',          'kilo',   null::text,       null::numeric),
    ('Ciruela',         'kilo',   null::text,       null::numeric),
    ('Durazno',         'kilo',   null::text,       null::numeric),
    ('Man Gob',         'kilo',   null::text,       null::numeric),
    ('Melón',           'kilo',   null::text,       null::numeric),
    ('Mzn Granny',      'kilo',   null::text,       null::numeric),
    ('Mzn Red',         'kilo',   null::text,       null::numeric),
    ('Pelón',           'kilo',   null::text,       null::numeric),
    ('Pera',            'kilo',   null::text,       null::numeric),
    ('Sandía',          'kilo',   null::text,       null::numeric),
    ('Uva',             'kilo',   null::text,       null::numeric),
    -- Sin envase compartido (envase perdido), por cubeta
    ('Frutilla',        'cubeta', null::text,       null::numeric),
    ('Arándano',        'cubeta', null::text,       null::numeric),
    -- Caja Chica Día, por kilo
    ('Lima',            'kilo',   'Caja Chica Día',  5::numeric),
    ('Tomate Redondo',  'kilo',   'Caja Chica Día',  6::numeric),
    ('Tomate Perita',   'kilo',   'Caja Chica Día',  6::numeric),
    ('Berenjena',       'kilo',   'Caja Chica Día',  6::numeric),
    ('Pepino',          'kilo',   'Caja Chica Día',  6::numeric),
    ('Zapallito',       'kilo',   'Caja Chica Día',  6::numeric),
    ('Morrón Verde',    'kilo',   'Caja Chica Día',  4::numeric),
    ('Tomate Cherry',   'kilo',   'Caja Chica Día',  5::numeric),
    -- Caja Chica Día, por unidad
    ('Mango',           'unidad', 'Caja Chica Día', 10::numeric),
    ('Palta',           'unidad', 'Caja Chica Día', 50::numeric),
    -- Caja Grande Día, por kilo
    ('Mandarina',       'kilo',   'Caja Grande Día', 16::numeric),
    ('Limón',           'kilo',   'Caja Grande Día', 16::numeric),
    ('Jugo',            'kilo',   'Caja Grande Día', 16::numeric),
    ('Ombligo',         'kilo',   'Caja Grande Día', 16::numeric),
    ('Pomelo',          'kilo',   'Caja Grande Día', 16::numeric),
    ('Morrón Rojo',     'kilo',   'Caja Grande Día',  8::numeric)
) as v(articulo_nombre, unidad_venta, envase_nombre, contenido_caja)
join articulos a on a.nombre = v.articulo_nombre
cross join (select id from clientes where nombre = 'Día') cl
left join envases e on e.nombre = v.envase_nombre and e.cliente_id = cl.id;

commit;
