-- Retiro de mercadería en el Mercado Central (Logística), previo a la
-- recepción en depósito. Orden real de los eventos: se carga la compra
-- (crear_compra, estado_retiro='pendiente') -> Logística la retira del
-- puesto del proveedor -> llega al depósito -> Depósito la recepciona.
--
-- Mismo patrón que estado/procesada_el (Recepción): una columna de
-- estado con CHECK, no columnas sueltas de timestamp — así es imposible
-- por diseño que una compra quede "retirada Y cancelada" a la vez (con
-- dos timestamps nullable en paralelo, nada lo impediría).
--
-- estado_retiro es un eje DISTINTO de estado (que sigue siendo solo
-- sobre la recepción en depósito) — nunca confundir las dos.
--
-- retiro_origen es nuevo (no existía para recepción): quién/qué marcó el
-- retiro — 'logistica' (a mano, desde /logistica), 'deposito'
-- (automático al recepcionar/rechazar: si llegó al depósito, alguien lo
-- retiró) o 'migracion' (backfill de compras viejas, ver abajo).
--
-- Sin DEFAULT a nivel de columna, mismo motivo que estado: las compras
-- nuevas reciben 'pendiente' explícito desde crear_compra(), no de un
-- default de la base. Verificado: los 4 métodos de carga (manual, foto
-- única, múltiples fotos, listado consolidado) pasan todos por
-- crear_compra() — no hay otro INSERT INTO compras en el código.
--
-- Seguro de correr más de una vez (add column if not exists, el UPDATE
-- de backfill no toca nada la segunda vez porque ya no queda ninguna
-- fila con estado_retiro NULL).

alter table compras add column if not exists estado_retiro text
    check (estado_retiro in ('pendiente', 'retirado', 'cancelado'));

alter table compras add column if not exists retiro_procesado_el timestamptz;

alter table compras add column if not exists retiro_origen text
    check (retiro_origen in ('logistica', 'deposito', 'migracion'));

comment on column compras.estado_retiro is 'pendiente/retirado/cancelado. Retiro = sacar la mercadería del puesto en el Mercado, ANTES de llegar al depósito (no confundir con estado, que es la recepción en depósito).';
comment on column compras.retiro_procesado_el is 'Cuándo se marcó retirado o cancelado. NULL = todavía pendiente.';
comment on column compras.retiro_origen is 'Quién/qué lo marcó: logistica (a mano, desde /logistica), deposito (automático al recepcionar/rechazar) o migracion (backfill de compras viejas).';

-- Backfill de las filas viejas: arrancamos de cero, se marcan como ya
-- retiradas para que no aparezcan en los 3 botones de /logistica.
-- retiro_procesado_el usa la fecha_operacion de cada compra (no now()),
-- para no dejar decenas de "retiros" con la hora de hoy en compras de
-- hace meses.
update compras
set estado_retiro = 'retirado',
    retiro_procesado_el = fecha_operacion::timestamptz,
    retiro_origen = 'migracion'
where estado_retiro is null;
