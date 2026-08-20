-- ============================================================================
-- Separar los proveedores del PUESTO de los proveedores de Compras.
--
-- Error de diseño original: Vacíos reusaba la tabla proveedores (Compras).
-- Son circuitos distintos — los proveedores del puesto están del otro lado
-- del Mercado y no tienen nada que ver con los proveedores de mercadería.
-- Tabla propia (solo nombre, con unificación por nombre normalizado como
-- clientes_puesto), y las cuatro tablas de Vacíos pasan a apuntarle.
--
-- Los proveedores del puesto los carga SOLO la cajera (pantalla propia):
-- el empleado del fondo elige de listas cerradas, nunca crea.
--
-- ORDEN ESPECIAL: este SQL ROMPE el código desplegado (espera los FKs
-- viejos). Correr en LAS DOS bases con el código nuevo ya pusheado, y
-- mergear inmediatamente después. Solo válido con el módulo VACÍO (la
-- verificación de lectura dio 0 en todas las tablas): dropea y recrea.
-- ============================================================================

begin;

create table proveedores_puesto (
    id                 bigint generated always as identity primary key,
    nombre             text not null,
    nombre_normalizado text not null unique,
    activo             boolean not null default true,
    creado_en          timestamptz not null default now()
);

comment on table proveedores_puesto is 'Proveedores del circuito del puesto (dueños de los cajones vacíos). NO son los proveedores de Compras (tabla proveedores): circuitos separados a propósito. Solo nombre; los carga la cajera, con unificación por nombre_normalizado.';
comment on column proveedores_puesto.nombre_normalizado is 'nombre en minúsculas, sin acentos ni espacios de más. El UNIQUE evita el mismo proveedor escrito de tres formas.';

-- Recrear las cuatro tablas apuntando a proveedores_puesto (estaban vacías).
drop table if exists conteos_vacios;
drop table if exists vacios_devueltos;
drop table if exists vacios_recibidos;
drop table if exists tipos_envase_puesto;

create table tipos_envase_puesto (
    id            bigint generated always as identity primary key,
    proveedor_id  bigint not null references proveedores_puesto (id),
    nombre        text not null,
    activo        boolean not null default true,
    creado_en     timestamptz not null default now(),
    unique (proveedor_id, nombre)
);

comment on table tipos_envase_puesto is 'Tipos de cajón físico por proveedor del puesto (los carga la cajera). Un proveedor sin tipos cargados no aparece en las pantallas de Vacíos.';

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

commit;
