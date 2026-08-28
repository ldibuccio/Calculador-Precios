-- ============================================================================
-- ETAPA 2 — La fecha de corte y el stock inicial.
--
-- A partir del CORTE (lunes 31/08/2026) rige el modelo nuevo. Lo anterior
-- no se borra ni se corrige: queda visible y consultable, pero fuera del
-- alcance del FIFO nuevo y de la rentabilidad real. Si el FIFO nuevo
-- alcanzara movimientos cargados con las reglas viejas, costearía contra
-- lotes que no son lo que dicen ser.
--
-- El stock que haya en el piso ese día entra como STOCK INICIAL, con su
-- costo cargado a mano, y con TIPO PROPIO. Esto último no es prolijidad:
-- los saldos iniciales de Vacíos se cargaron por la pantalla de Ajustes y
-- hoy son indistinguibles de una corrección de faltante — cualquier
-- reporte de mermas va a sumar esos 923 cajones como perdidos (ver
-- "Deuda pendiente de limpieza" en db/APLICADO.md). Acá se separa desde
-- el día uno, que es cuando sale gratis.
--
-- CINCO CAMBIOS. Los tres primeros son los que hacen que el stock inicial
-- SIN PROCESAR pueda existir y tener costo; el cuarto es el stock inicial
-- YA PROCESADO (cajas armadas); el quinto es dónde vive la fecha.
--
-- ADITIVA: no modifica ninguna fila existente. Los datos que hay hoy
-- siguen cumpliendo todos los checks nuevos. No rompe el código
-- desplegado: nada lee todavía el tipo nuevo ni la tabla nueva.
-- ============================================================================

begin;

-- ---------------------------------------------------------------------------
-- 1. El tipo de movimiento nuevo.
--    Sin esto, el stock inicial entraría como 'ajuste' y en tres meses
--    sería indistinguible de una corrección. Es EL error de Vacíos.
-- ---------------------------------------------------------------------------
alter table movimientos_stock
    drop constraint movimientos_stock_tipo_check;

alter table movimientos_stock
    add constraint movimientos_stock_tipo_check
    check (tipo in ('ajuste', 'merma', 'reingreso_rechazo', 'stock_inicial'));

-- ---------------------------------------------------------------------------
-- 2. Que el stock inicial pueda LLEVAR COSTO.
--    El check viejo permitía costo_por_bulto SOLO en el reingreso por
--    rechazo. Sin tocarlo, el stock inicial nacería sin costo y el FIFO
--    del modelo nuevo arrancaría costeando contra lotes sin precio — el
--    día uno, y para siempre.
--    pedido_renglon_id sigue siendo exclusivo del reingreso: eso apunta a
--    un renglón que volvió, y el stock inicial no vuelve de ningún lado.
-- ---------------------------------------------------------------------------
alter table movimientos_stock
    drop constraint movimientos_stock_vinculo_solo_reingreso;

alter table movimientos_stock
    add constraint movimientos_stock_vinculo_solo_reingreso
    check (
        (tipo = 'reingreso_rechazo' or pedido_renglon_id is null)
        and (tipo in ('reingreso_rechazo', 'stock_inicial') or costo_por_bulto is null)
    );

-- ---------------------------------------------------------------------------
-- 3. Que una merma dirigida pueda apuntar a un lote de stock inicial.
--    El operario que ve podrirse un lote lo elige; si el lote es del
--    stock inicial y no está en esta lista, esa merma no se puede
--    registrar dirigida y cae a FIFO, costeando contra el lote
--    equivocado.
-- ---------------------------------------------------------------------------
alter table movimientos_stock
    drop constraint movimientos_stock_lote_tipo_check;

alter table movimientos_stock
    add constraint movimientos_stock_lote_tipo_check
    check (lote_tipo is null
           or lote_tipo in ('guia', 'reproceso', 'reingreso_rechazo', 'ajuste', 'stock_inicial'));

-- ---------------------------------------------------------------------------
-- 4. El reproceso inicial: PRODUCE SIN CONSUMIR.
--    Las cajas armadas que hay en el piso el día del corte ya existen, y
--    los cajones que las originaron no se van a cargar nunca. Un
--    reproceso normal descuenta lo que tomó; si el inicial descontara
--    igual, dejaría el artículo en negativo o se comería el stock inicial
--    sin procesar recién cargado.
--
--    Se expresa EN LOS DATOS, no en el código: un inicial toma CERO. El
--    cálculo de stock ya resta SUM(bultos_tomados), así que un cero ahí
--    es exactamente "no consumió nada" — sin ninguna excepción escrita en
--    una consulta que alguien pueda olvidar.
--
--    Y el check lo obliga en los dos sentidos: un inicial no puede tomar
--    nada, y un reproceso normal tiene que tomar algo.
-- ---------------------------------------------------------------------------
alter table reprocesos
    add column tipo text not null default 'normal'
    check (tipo in ('normal', 'inicial'));

alter table reprocesos
    drop constraint reprocesos_bultos_tomados_check;

alter table reprocesos
    add constraint reprocesos_bultos_tomados_check
    check ((tipo = 'inicial' and bultos_tomados = 0)
           or (tipo = 'normal' and bultos_tomados > 0));

comment on column reprocesos.tipo is
    'normal = el reproceso de todos los días: toma bultos del stock y produce primera, segunda y merma. inicial = las cajas que ya estaban armadas en el piso el día del corte (31/08/2026): PRODUCEN SIN CONSUMIR (bultos_tomados = 0), porque los cajones que las originaron nunca se cargaron. El check obliga las dos cosas.';

-- ---------------------------------------------------------------------------
-- 5. Dónde vive la fecha de corte.
--    Una sola fila, como revision_tick: el código la lee de UN lugar y no
--    queda escrita a mano en veinte consultas.
-- ---------------------------------------------------------------------------
create table corte_modelo (
    id integer primary key check (id = 1),
    fecha date not null,
    creado_en timestamptz not null default now()
);

insert into corte_modelo (id, fecha) values (1, '2026-08-31');

comment on table corte_modelo is
    'La fecha de corte del modelo nuevo (una sola fila, id = 1). A partir de ella rige el FIFO nuevo y la rentabilidad real; lo anterior queda visible pero fuera de alcance, porque se cargó con reglas que dejaban salir pedidos contra cualquier mercadería. Vive en la base y no en el código para que se lea de un solo lugar.';

commit;
