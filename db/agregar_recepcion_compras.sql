-- Depósito / Recepción: estado de cada compra (pendiente/recepcionado/
-- rechazado) y los valores REALES que pesa/cuenta Depósito al recibir.
--
-- El estimado (cantidad_cajones, contenido_por_cajon, cantidad_kilos,
-- cantidad_fraccion) NUNCA se pisa: se agrega un juego de columnas "_real"
-- en espejo, que se completa recién al recepcionar. cantidad_cajones_real y
-- el total pesado/contado (cantidad_kilos_real o cantidad_fraccion_real,
-- según unidad_compra del artículo) los tipea Depósito; contenido_por_cajon_real
-- se calcula solo (total_real / cantidad_cajones_real) para mantener la
-- misma simetría que el par estimado — así el costeo (que arma su cuenta
-- como cajones × contenido, ver app/costeo.py) no necesita ningún cambio de
-- fórmula, alcanza con leer las columnas reales en vez de las estimadas.
--
-- estado va SIN default a nivel columna a propósito: un ALTER TABLE ADD
-- COLUMN con NOT NULL DEFAULT 'pendiente' en Postgres 11+ aplica ese
-- default también a las filas YA EXISTENTES (las dejaría a todas como
-- "pendiente"), y las compras cargadas antes de este cambio nunca pasaron
-- por Depósito — tienen que quedar en NULL. El valor 'pendiente' se
-- escribe explícitamente en cada INSERT nuevo, desde crear_compra() en
-- app/db.py (mismo criterio ya usado con guia_id).
--
-- Con esto, la consulta de Recepción (compras pendientes) queda:
--   WHERE estado = 'pendiente'
-- Alcanza solo con esa condición: NULL nunca es igual a 'pendiente' en
-- SQL, así que las compras viejas (estado NULL) quedan afuera solas.
--
-- Seguro de correr más de una vez (add column if not exists).

alter table compras add column if not exists estado text
    check (estado in ('pendiente', 'recepcionado', 'rechazado'));

alter table compras add column if not exists cantidad_cajones_real numeric;
alter table compras add column if not exists contenido_por_cajon_real numeric;
alter table compras add column if not exists cantidad_kilos_real numeric;
alter table compras add column if not exists cantidad_fraccion_real numeric;
alter table compras add column if not exists procesada_el timestamptz;

comment on column compras.estado is 'pendiente/recepcionado/rechazado. NULL en compras cargadas antes de este cambio (nunca pasaron por Depósito) — se completa a ''pendiente'' recién al cargar la compra, desde crear_compra.';
comment on column compras.cantidad_cajones_real is 'Cajones realmente recibidos, si Depósito los ajustó al recepcionar. NULL = no se ajustó, o todavía no se recepcionó.';
comment on column compras.contenido_por_cajon_real is 'Contenido por cajón real, derivado (cantidad_kilos_real o cantidad_fraccion_real dividido cantidad_cajones_real) al recepcionar. No se pide a mano.';
comment on column compras.cantidad_kilos_real is 'Kilos reales pesados por Depósito (solo artículos que se compran por kilo). NULL = todavía no pesado, o el artículo no se compra por kilo.';
comment on column compras.cantidad_fraccion_real is 'Unidades/cubetas reales contadas por Depósito (solo artículos que se compran por unidad o cubeta). NULL = todavía no recepcionado, o el artículo se compra por kilo.';
comment on column compras.procesada_el is 'Cuándo se recepcionó o rechazó esta compra en Depósito. NULL = todavía pendiente.';
