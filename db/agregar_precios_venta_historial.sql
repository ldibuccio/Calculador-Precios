-- Agrega precios_venta_historial: precio de venta vigente por artículo y
-- cliente, con historial de vigencia (mismo patrón que
-- clientes_parametros_historial y envases_costo_historial: columna
-- vigente_desde, nunca se pisa un valor viejo, se agrega una fila nueva. El
-- vigente para una fecha es la fila con vigente_desde más reciente que ya
-- llegó para ese articulo_id + cliente_id).
--
-- Solo aditiva: no toca precios_dia (queda como está, sin usarse) ni
-- ninguna otra tabla. Segura de correr más de una vez (create table if not
-- exists, create index if not exists).

create table if not exists precios_venta_historial (
    id              bigint generated always as identity primary key,
    articulo_id     bigint not null references articulos (id),
    cliente_id      bigint not null references clientes (id),
    precio          numeric not null,
    vigente_desde   date not null,
    creado_en       timestamptz not null default now(),
    unique (articulo_id, cliente_id, vigente_desde)
);

comment on table precios_venta_historial is 'Precio de venta por artículo y cliente, con historial por fecha de vigencia. El vigente es la fila con vigente_desde más reciente que ya llegó.';

create index if not exists precios_venta_historial_vigente_idx
    on precios_venta_historial (cliente_id, articulo_id, vigente_desde desc);
