-- ============================================================================
-- ETAPA 1 — ficha_id en reprocesos.
--
-- Es la piedra angular del modelo nuevo: sin esto el sistema NUNCA puede
-- decir cuántas cajas de una ficha tiene, y todo lo que sigue se apoya en
-- derivar la ficha de (articulo_id, cliente_id) — una derivación que es
-- AMBIGUA POR DISEÑO y lo va a ser siempre: un cliente puede pedir una
-- ficha y recibir otra del mismo artículo, y por eso fichas_logistica no
-- tiene unique (articulo_id, cliente_id).
--
-- NULLABLE a propósito, con DOS significados que se distinguen por la
-- FECHA DE CORTE (31/08/2026), no por una segunda columna:
--   * reproceso ANTERIOR al corte  -> nunca se va a completar, y no
--     entra en el modelo nuevo.
--   * reproceso POSTERIOR al corte -> quedó SIN ASIGNAR, y hay que
--     completarlo (lo va a contar una alerta en la etapa 6).
--
-- LA FK NO LLEVA "ON DELETE SET NULL", A DIFERENCIA DE
-- pedidos_renglones.ficha_id. Acá el NULL tiene significado propio ("sin
-- asignar"): si borrar una ficha nuleara sus reprocesos en silencio, un
-- reproceso perfectamente asignado se volvería indistinguible de uno que
-- el operario dejó sin asignar, y de paso cambiaría el stock de esa
-- ficha sin que nadie lo pida. Sin cláusula = NO ACTION: la base se niega
-- a borrar una ficha que tenga guías R.
--
-- OJO, ESTO CAMBIA UNA CONDUCTA EXISTENTE: hoy eliminar_ficha() hace
-- borrado real y su docstring dice "nada más referencia su id". Desde
-- esta migración eso deja de ser cierto, y borrar una ficha con guías R
-- va a fallar. El código de la etapa lo tiene que atajar y mostrarlo como
-- 400 con el número de guías, igual que ya hace la baja de un tipo de
-- envase con saldo — nunca un 500.
--
-- ADITIVO PURO: agrega una columna nullable y un índice. No modifica ni
-- una fila existente. No rompe el código desplegado: hoy nadie lee esta
-- columna.
-- ============================================================================

begin;

alter table reprocesos
    add column ficha_id bigint references fichas_logistica (id);

-- Parcial: los reprocesos sin asignar no se buscan por ficha, y el índice
-- que importa es el de "cuántas cajas hay de esta ficha".
create index reprocesos_ficha_idx
    on reprocesos (ficha_id) where ficha_id is not null;

comment on column reprocesos.ficha_id is
    'A qué ficha fueron las cajas de primera de esta guía R. NULL tiene dos significados que separa la fecha de corte (31/08/2026): antes del corte = dato viejo que no se completa; después = SIN ASIGNAR, y hay que completarlo. No se deriva de (articulo_id, cliente_id): un cliente puede tener varias fichas del mismo artículo, así que esa derivación es ambigua por diseño.';

commit;
