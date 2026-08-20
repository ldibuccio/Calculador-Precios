-- ============================================================================
-- Módulo Vacíos (Envases Puesto): cajones de proveedores que entran y salen
-- del puesto del Mercado.
--
-- Operatoria: se vende mercadería con seña por el cajón; el cliente devuelve
-- el cajón vacío (entrada, vacios_recibidos) y se le devuelve la seña; los
-- cajones son del proveedor y él los retira con su camión (salida,
-- vacios_devueltos). El stock es la diferencia, calculada siempre — no hay
-- columna de stock que se pueda desincronizar.
--
-- NADA de esto se comparte con la pantalla Envases de Comercial (aquella es
-- el costo del envase que se le factura al cliente de distribución): son
-- cajones físicos, tablas propias.
--
-- Los proveedores son los MISMOS de Compras (tabla proveedores existente):
-- son los mismos puestos del Mercado, ya cargados con su código.
--
-- Correr en LAS DOS bases (Frutamax y Palmala) ANTES de mergear el código.
-- Inofensivo para el código que corre hoy: tablas nuevas que nadie lee.
-- ============================================================================

begin;

create table tipos_envase_puesto (
    id            bigint generated always as identity primary key,
    proveedor_id  bigint not null references proveedores (id),
    nombre        text not null,
    activo        boolean not null default true,
    creado_en     timestamptz not null default now(),
    unique (proveedor_id, nombre)
);

comment on table tipos_envase_puesto is 'Tipos de cajón físico que maneja cada proveedor (los carga el dueño). Un proveedor sin tipos cargados no aparece en las pantallas de Vacíos.';

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
    proveedor_id       bigint not null references proveedores (id),
    tipo_envase_id     bigint not null references tipos_envase_puesto (id),
    cantidad           integer not null check (cantidad > 0),
    creado_en          timestamptz not null default now(),
    sena_pagada_el     timestamptz,
    anulado_el         timestamptz
);

comment on table vacios_recibidos is 'Entrada: un cliente trae cajones vacíos al puesto. La seña se le devuelve después (ver sena_pagada_el).';
comment on column vacios_recibidos.sena_pagada_el is 'NULL = seña pendiente de pagar al cliente; con fecha = cuándo la cajera la pagó.';
comment on column vacios_recibidos.anulado_el is 'NULL = movimiento vigente. Los movimientos nunca se borran físicamente: anular deja el registro visible como corrección y el stock lo excluye.';

create table vacios_devueltos (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint not null references proveedores (id),
    tipo_envase_id  bigint not null references tipos_envase_puesto (id),
    cantidad        integer not null check (cantidad > 0),
    stock_sistema   integer not null,
    creado_en       timestamptz not null default now(),
    anulado_el      timestamptz
);

comment on table vacios_devueltos is 'Salida: el proveedor retira sus cajones con el camión.';
comment on column vacios_devueltos.stock_sistema is 'Stock del sistema (recibidos − devueltos, sin este movimiento) EN el instante de guardar. Si la devolución supera este número, esa diferencia queda registrada acá — no es solo un cartel que se cierra.';
comment on column vacios_devueltos.anulado_el is 'NULL = movimiento vigente. Igual que en vacios_recibidos: anular, nunca borrar.';

create table conteos_vacios (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint not null references proveedores (id),
    tipo_envase_id  bigint not null references tipos_envase_puesto (id),
    cantidad        integer not null check (cantidad >= 0),
    stock_sistema   integer not null,
    creado_en       timestamptz not null default now()
);

comment on table conteos_vacios is 'Conteo físico que carga el empleado SIN ver el stock del sistema (control cruzado: si lo ve, transcribe en vez de contar).';
comment on column conteos_vacios.stock_sistema is 'Stock del sistema EN el instante del conteo, guardado del lado del server (el empleado nunca lo ve). El cotejo compara contra esta foto exacta, aunque después entren movimientos.';

commit;
