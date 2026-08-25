-- ============================================================================
-- STOCK DEL DEPÓSITO (módulo nuevo) — tanda 1
-- ============================================================================
-- El stock por artículo NO se guarda: se calcula siempre, derivado de lo que
-- ya existe (compras recepcionadas como entradas, renglones de pedido armados
-- como salidas) más los movimientos que no existían en ningún lado, que van
-- en la tabla nueva movimientos_stock:
--
--   * ajuste: corrección con motivo (también el stock inicial). Con signo.
--   * merma: cajones que se tiraron. Siempre negativa.
--   * reingreso_rechazo: mercadería que el cliente devolvió. Siempre
--     positiva, con el cliente y su PROPIA fecha de operación (el camión
--     puede volver un día y cargarse al siguiente; con la fecha real no se
--     desordena el FIFO ni el cotejo del día anterior).
--
-- Los movimientos nunca PISAN el stock: cada uno es una fila más, con la
-- foto del stock del sistema del momento (stock_sistema, SIN este
-- movimiento) y baja lógica (anulado_el) — mismo diseño que ajustes_vacios.
--
-- conteos_stock es el Stock Físico (tanda 3, la tabla va ya para migrar una
-- sola vez): lo que el operario CONTÓ, con la foto del sistema del instante
-- del conteo — mismo diseño que conteos_vacios.
--
-- El reproceso (módulo 2) van a ser tipos nuevos en movimientos_stock; el
-- check de tipo se amplía en esa migración.
--
-- Los índices de compras y pedidos_renglones son para que el stock por
-- artículo (SUM con GROUP BY) salga por index-only scan aunque las tablas
-- crezcan.
--
-- ADITIVO PURO: no modifica filas existentes. Correr en las DOS bases
-- (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

create table movimientos_stock (
    id bigint generated always as identity primary key,
    articulo_id bigint not null references articulos(id),
    tipo text not null check (tipo in ('ajuste', 'merma', 'reingreso_rechazo')),
    cantidad numeric not null check (cantidad <> 0),
    motivo text not null check (btrim(motivo) <> ''),
    cliente_id bigint references clientes(id),
    fecha_operacion date not null,
    stock_sistema numeric not null,
    creado_en timestamptz not null default now(),
    anulado_el timestamptz,
    constraint movimientos_stock_merma_negativa check (tipo <> 'merma' or cantidad < 0),
    constraint movimientos_stock_reingreso_positivo check (tipo <> 'reingreso_rechazo' or cantidad > 0),
    constraint movimientos_stock_cliente_solo_reingreso check (tipo = 'reingreso_rechazo' or cliente_id is null)
);

create table conteos_stock (
    id bigint generated always as identity primary key,
    articulo_id bigint not null references articulos(id),
    cantidad numeric not null check (cantidad >= 0),
    stock_sistema numeric not null,
    creado_en timestamptz not null default now()
);

create index movimientos_stock_stock_idx
    on movimientos_stock (articulo_id) include (cantidad)
    where anulado_el is null;

create index compras_stock_deposito_idx
    on compras (articulo_id) include (cantidad_cajones_real)
    where estado = 'recepcionado';

create index pedidos_renglones_stock_idx
    on pedidos_renglones (articulo_id)
    where armado_el is not null and anulado_el is null;

comment on table movimientos_stock is
    'Movimientos de stock del depósito que no salen de otra tabla: ajustes (incluido el stock inicial), mermas y reingresos por rechazo del cliente. En BULTOS. Nunca pisan el stock: el stock por artículo se calcula siempre (compras recepcionadas + estos movimientos − renglones armados).';
comment on column movimientos_stock.cantidad is
    'Bultos, con signo: ajuste ±, merma siempre negativa, reingreso siempre positivo.';
comment on column movimientos_stock.fecha_operacion is
    'Fecha REAL del hecho (puede no ser la de carga): ordena el FIFO y el cotejo.';
comment on column movimientos_stock.stock_sistema is
    'Foto del stock del sistema del artículo al momento de cargar el movimiento, SIN este movimiento. Rastro para el control cruzado.';
comment on column movimientos_stock.cliente_id is
    'Solo para reingreso_rechazo: qué cliente devolvió la mercadería.';
comment on table conteos_stock is
    'Stock Físico del depósito: lo que el operario contó (en bultos), sin ver el sistema. stock_sistema es la foto del sistema en el instante del conteo, para el Cotejo.';

-- Verificación: las dos tablas y los tres índices creados.
-- select table_name from information_schema.tables
--  where table_name in ('movimientos_stock', 'conteos_stock');
-- select indexname from pg_indexes
--  where indexname in ('movimientos_stock_stock_idx', 'compras_stock_deposito_idx',
--                      'pedidos_renglones_stock_idx');
