-- ============================================================================
-- DESTINO DEL RECHAZO + MERMA POR LOTE (decisión del 26/08)
-- ============================================================================
-- Cuatro columnas nuevas en movimientos_stock, todas nullable y aditivas.
--
-- (A) DESTINO DEL RECHAZO — solo tipo 'reingreso_rechazo'
--
-- Qué se hace con la mercadería que volvió se decide EN EL MOMENTO de
-- cargar el reingreso, no después:
--
-- 1. destino_rechazo = 'stock': queda tal cual para volver a mandarla a
--    otra sucursal o cliente. Es lo que hace hoy el sistema, y es el
--    default de los reingresos ya cargados (NULL se lee como 'stock'). El
--    costo NO se pierde: la mercadería vuelve al stock y se va a vender,
--    solo se perdió la venta de ese día.
-- 2. destino_rechazo = 'segunda': pasa al pool de segunda tal como está,
--    con su caja y su kilaje, para remitir al Puesto.
-- 3. destino_rechazo = 'reproceso': las cajas chicas vuelven a cajón
--    grande y esos cajones entran al pool de segunda. NO pasa por la tabla
--    reprocesos: la toma de un reproceso consume FIFO del stock general y
--    se comería el lote más viejo en vez de este rechazo, y con primera=0
--    el costo se evaporaría (el reproceso es neutro a propósito porque el
--    costo viaja a la primera). Se resuelve acá, con el vínculo al pedido
--    y el costo ya congelados.
--
-- bultos_segunda: cuántos bultos entran al pool. En 'segunda' es la misma
-- cantidad devuelta (misma caja); en 'reproceso' son los cajones grandes
-- que salieron, que el operario carga (volvieron 40 cajas, quedaron 12
-- cajones — la diferencia no es merma, es cambio de envase). En 'stock'
-- va NULL: no entra al pool.
--
-- Un reingreso con destino 'segunda' o 'reproceso' NO entra al stock
-- normal: sale del cálculo de stock y suma al pool de segunda. Y como no
-- queda primera que absorba el costo, todo el costo de esos bultos es
-- pérdida directa: la Rentabilidad Real lo muestra en su línea propia
-- "− rechazos perdidos" (mercadería congelada + envase a la fecha del
-- pedido, sin tasas del cliente), separada de las mermas.
--
-- Rechazo parcial: se cargan dos reingresos del mismo renglón (6 a stock,
-- 4 a segunda). El tope duro del server (armado − ya devuelto acumulado)
-- ya es compartido, así que la suma nunca puede pasarse de lo armado.
--
-- (B) MERMA POR LOTE — solo tipo 'merma'
--
-- Hoy la merma sale del artículo y el FIFO toma del lote más viejo. Si se
-- pudrió una guía R armada hace dos días, hay que poder mermar ESE lote:
--
-- lote_tipo + lote_origen_id: a qué lote se dirige la merma. NULL (el
-- default de la pantalla y de todas las mermas ya cargadas) = FIFO como
-- siempre, el operario no elige nada. Con lote elegido, la merma se
-- descuenta primero de ese lote y solo el excedente cae a FIFO: registra
-- y delata, jamás traba. Además la merma dirigida a una guía R se cuesta
-- al costo de primera de esa guía, que es la pérdida real — no la del
-- cajón viejo que el FIFO hubiera elegido.
--
-- lote_tipo son los mismos tipos de lote del detalle FIFO por artículo:
-- 'guia' (compra recepcionada), 'reproceso' (primera de una guía R),
-- 'reingreso_rechazo' y 'ajuste' (positivo). lote_origen_id es el id en
-- la tabla de ese tipo (compras, reprocesos o movimientos_stock): es
-- polimórfico a propósito, sin FK — el lote se resuelve rejugando el
-- FIFO, que es lo único que sabe qué lotes existen hoy.
--
-- ADITIVO PURO: no modifica ninguna fila existente ni cambia el
-- comportamiento del código viejo (todo NULL = como hoy). Correr en las
-- DOS bases (Frutamax y Palmala) y marcar en APLICADO.md. El código que
-- usa estas columnas se mergea recién después de la confirmación.
-- ============================================================================

alter table movimientos_stock
    add column destino_rechazo text
        check (destino_rechazo is null or destino_rechazo in ('stock', 'segunda', 'reproceso')),
    add column bultos_segunda numeric
        check (bultos_segunda is null or bultos_segunda > 0),
    add column lote_tipo text
        check (lote_tipo is null or lote_tipo in ('guia', 'reproceso', 'reingreso_rechazo', 'ajuste')),
    add column lote_origen_id bigint;

-- El destino y su pool son cosa del reingreso: un ajuste o una merma
-- jamás mandan nada a segunda.
alter table movimientos_stock
    add constraint movimientos_stock_destino_solo_reingreso
        check (tipo = 'reingreso_rechazo' or (destino_rechazo is null and bultos_segunda is null));

-- Los bultos al pool acompañan al destino: obligatorios cuando va a
-- segunda (por sí misma o por reproceso a cajón), prohibidos cuando queda
-- en stock. Sin esto, un rechazo podría decir "va a segunda" y no sumar
-- nada al pool.
alter table movimientos_stock
    add constraint movimientos_stock_segunda_segun_destino
        check (
            case
                when destino_rechazo in ('segunda', 'reproceso')
                    then bultos_segunda is not null
                else bultos_segunda is null
            end
        );

-- El lote dirigido es solo de la merma, y sus dos columnas van juntas o
-- ninguna (un tipo sin id no identifica ningún lote).
alter table movimientos_stock
    add constraint movimientos_stock_lote_dirigido_solo_merma
        check (tipo = 'merma' or (lote_tipo is null and lote_origen_id is null));

alter table movimientos_stock
    add constraint movimientos_stock_lote_dirigido_completo
        check ((lote_tipo is null) = (lote_origen_id is null));

-- El pool de segunda se suma en cada entrada al Stock del Sistema y a
-- Remito de Segunda: que salga por index-only scan aunque la tabla crezca.
create index movimientos_stock_rechazo_segunda_idx
    on movimientos_stock (articulo_id) include (bultos_segunda)
    where destino_rechazo in ('segunda', 'reproceso') and anulado_el is null;

comment on column movimientos_stock.destino_rechazo is
    'Solo reingreso_rechazo: qué se hizo con lo que volvió — stock (queda para volver a mandarla, el costo no se pierde), segunda (al pool tal cual) o reproceso (vuelve a cajón grande y esos cajones van al pool). NULL en los reingresos viejos = stock. Segunda y reproceso salen del stock normal y su costo entero es pérdida ("− rechazos perdidos" en la Real).';
comment on column movimientos_stock.bultos_segunda is
    'Solo reingreso_rechazo con destino segunda/reproceso: cuántos bultos entran al pool de segunda. En segunda es la cantidad devuelta (misma caja); en reproceso son los cajones grandes que salieron (la diferencia con lo devuelto es cambio de envase, no merma).';
comment on column movimientos_stock.lote_tipo is
    'Solo merma: a qué tipo de lote se dirige (guia, reproceso, reingreso_rechazo, ajuste). NULL = FIFO como siempre, del lote más viejo — es el default de la pantalla y de todas las mermas viejas.';
comment on column movimientos_stock.lote_origen_id is
    'Solo merma: id del lote elegido en la tabla de su lote_tipo (compras, reprocesos o movimientos_stock). Polimórfico a propósito, sin FK: el lote se resuelve rejugando el FIFO. Si el lote no cubre la merma, el excedente cae a FIFO — nunca traba.';

-- Verificación: las cuatro columnas y el índice creados.
-- select column_name from information_schema.columns
--  where table_name = 'movimientos_stock'
--    and column_name in ('destino_rechazo', 'bultos_segunda', 'lote_tipo', 'lote_origen_id')
--  order by column_name;
-- select indexname from pg_indexes where indexname = 'movimientos_stock_rechazo_segunda_idx';
