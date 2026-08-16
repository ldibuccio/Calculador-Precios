-- Número de guía para Depósito: una guía por proveedor por día de operación.
--
-- guias_compra.id ES el número de guía (ej. 105) — autoincremental, único,
-- gratis vía "identity". unique(fecha_operacion, proveedor_id) asegura que
-- todo lo que un proveedor entrega en el mismo día cae en la MISMA guía,
-- sin importar si se cargó en una sola vez o en varias (foto, múltiples
-- fotos, listado consolidado, o carga manual a lo largo del día) — es la
-- misma agrupación que ya usa "Cancelar" en /compras/nueva.
--
-- compras.guia_id + compras.guia_punto (el ".1"/".2"/".3" dentro de la
-- guía) se completan solos al guardar cada compra, dentro de crear_compra
-- (ver app/db.py) — no hace falta tocar nada más para que se asignen.
-- guia_punto se graba una sola vez al cargar y no se recalcula después: si
-- se borra un renglón del medio, los que quedan NO se renumeran (un hueco
-- en la numeración es normal y esperable, no es un bug).
--
-- Ambas columnas nullable a propósito: las compras cargadas antes de este
-- cambio quedan con guia_id/guia_punto en NULL, sin backfill retroactivo
-- (no tiene sentido inventarles un número de guía a compras que nunca
-- tuvieron un papel físico que journalear en Depósito).
--
-- Este paso es solo base de datos + asignación al guardar: la guía
-- todavía no se muestra en ninguna pantalla (Últimas Compras, Buscar
-- Compras, exports).
--
-- Seguro de correr más de una vez (create table if not exists, add column
-- if not exists).

create table if not exists guias_compra (
    id               bigint generated always as identity primary key,
    fecha_operacion  date not null,
    proveedor_id     bigint not null references proveedores(id),
    creada_el        timestamptz not null default now(),
    unique (fecha_operacion, proveedor_id)
);

comment on table guias_compra is 'Una guía por proveedor por día de operación. El id es el número de guía (ej. 105).';

alter table compras add column if not exists guia_id bigint references guias_compra(id);
alter table compras add column if not exists guia_punto integer;

comment on column compras.guia_id is 'Guía de esta compra (proveedor+día). NULL en compras cargadas antes de este cambio.';
comment on column compras.guia_punto is 'Punto dentro de la guía (105.1, 105.2, ...). Se fija una sola vez al cargar, no se renumera si se borra otro renglón.';
