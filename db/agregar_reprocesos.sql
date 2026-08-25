-- ============================================================================
-- REPROCESO (módulo 2) — tanda 1
-- ============================================================================
-- El depósito toma bultos del stock y los transforma: 30 cajones de tomate
-- de 16 kg → 20 cajas chicas de 6 kg (primera) + 5 de segunda + 5 de merma.
-- El artículo es SIEMPRE el mismo (verificado contra el catálogo: la
-- presentación por cliente vive en la ficha logística, no en el artículo);
-- lo que cambia es el tamaño del bulto, y el stock cuenta bultos. No hay
-- ningún check que correlacione cantidades: no hay correlación real.
--
-- reprocesos es la GUÍA R: el id autonumerado ES el número (R1, R2...).
-- Nunca se borra (baja lógica con anulado_el) así la numeración no se
-- agujerea. reprocesos_consumos es la trazabilidad hacia atrás: de qué
-- lote salió cada bulto tomado ("de la 105 tomé 30, de la 118 tomé 20"),
-- ESCRITA POR EL SERVER corriendo el FIFO al cargar — el operario no
-- elige lote jamás. Apunta a la COMPRA (no a la guía) porque un reproceso
-- puede mezclar proveedores; también puede consumir de un ajuste (stock
-- inicial), de un reingreso o de la primera de otra guía R.
--
-- COSTO (decisión del dueño): todo a la primera; segunda y merma valen
-- cero; mezcla de lotes = promedio ponderado. El costo se CONGELA al
-- cargar (costo_por_bulto en cada consumo, del importe de esa compra).
-- Si algún lote no tiene precio todavía (compra de la mañana sin importe,
-- stock inicial, reingreso), costo_total y costo_por_bulto_primera quedan
-- NULL = "costo incompleto", visible — nunca se inventa un número.
-- Este costo NO alimenta la cotización: vive acá y el costeo solo lee la
-- tabla compras. El stock vivo tampoco lee los consumos: se deriva de las
-- cabeceras (− tomados, + primera) y el FIFO se recalcula siempre.
--
-- remitos_segunda (tanda 2): la segunda que se manda al Puesto (destino
-- fijo, por eso no es campo). La segunda es un pool aparte por artículo:
-- Σ bultos_segunda vigentes − Σ remitos vigentes.
--
-- ADITIVO PURO: no modifica filas existentes. Correr en las DOS bases
-- (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

create table reprocesos (
    id bigint generated always as identity primary key,
    articulo_id bigint not null references articulos(id),
    fecha_operacion date not null,
    bultos_tomados numeric not null check (bultos_tomados > 0),
    bultos_primera numeric not null check (bultos_primera >= 0),
    bultos_segunda numeric not null check (bultos_segunda >= 0),
    bultos_merma numeric not null check (bultos_merma >= 0),
    costo_total numeric,
    costo_por_bulto_primera numeric,
    creado_en timestamptz not null default now(),
    anulado_el timestamptz
);

create table reprocesos_consumos (
    id bigint generated always as identity primary key,
    reproceso_id bigint not null references reprocesos(id),
    origen text not null check (origen in ('compra', 'ajuste', 'reingreso_rechazo', 'reproceso', 'sin_lote')),
    compra_id bigint references compras(id),
    origen_id bigint,
    bultos numeric not null check (bultos > 0),
    costo_por_bulto numeric,
    constraint reprocesos_consumos_compra_coherente check ((origen = 'compra') = (compra_id is not null))
);

create table remitos_segunda (
    id bigint generated always as identity primary key,
    articulo_id bigint not null references articulos(id),
    bultos numeric not null check (bultos > 0),
    fecha_operacion date not null,
    creado_en timestamptz not null default now(),
    anulado_el timestamptz
);

create index reprocesos_stock_idx
    on reprocesos (articulo_id)
    include (bultos_tomados, bultos_primera, bultos_segunda)
    where anulado_el is null;

create index reprocesos_consumos_reproceso_idx
    on reprocesos_consumos (reproceso_id);

create index remitos_segunda_stock_idx
    on remitos_segunda (articulo_id) include (bultos)
    where anulado_el is null;

comment on table reprocesos is
    'Guías R: transformaciones del depósito (tomo bultos del stock, armo cajas de primera + segunda + merma, mismo artículo). El id es el número de guía. El stock se deriva de acá (− tomados, + primera); la segunda es un pool aparte.';
comment on column reprocesos.costo_total is
    'Costo congelado al cargar: Σ (bultos × costo_por_bulto) de los consumos. NULL = costo incompleto (algún lote sin precio). TODO el costo va a la primera; segunda y merma valen cero. NUNCA lo lee la cotización.';
comment on column reprocesos.costo_por_bulto_primera is
    'costo_total / bultos_primera, congelado. NULL si el costo está incompleto o no hubo primera.';
comment on table reprocesos_consumos is
    'De qué lote salió cada bulto tomado, escrito por el server corriendo FIFO al cargar (el operario no elige lote). Documento congelado: si después se corrige una recepción, el stock vivo se reacomoda pero esta trazabilidad y su costo no se mueven.';
comment on column reprocesos_consumos.origen is
    'compra (lote de guía de compra), ajuste (ej. stock inicial), reingreso_rechazo, reproceso (primera de otra guía R), o sin_lote (se tomó más de lo que los lotes cubrían: el piso es la verdad, no se traba).';
comment on table remitos_segunda is
    'Segunda remitida al Puesto (destino fijo): sale del pool de segunda y deja de ser problema del depósito. El recupero económico va aparte, más adelante.';

-- Verificación: las tres tablas y los tres índices creados.
-- select table_name from information_schema.tables
--  where table_name in ('reprocesos', 'reprocesos_consumos', 'remitos_segunda');
-- select indexname from pg_indexes
--  where indexname in ('reprocesos_stock_idx', 'reprocesos_consumos_reproceso_idx',
--                      'remitos_segunda_stock_idx');
