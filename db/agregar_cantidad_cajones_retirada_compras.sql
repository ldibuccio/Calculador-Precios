-- Logística: cuántos cajones anotó el que retira como efectivamente
-- retirados del puesto. Dato aparte de cantidad_cajones (lo que cargó el
-- comprador) y cantidad_cajones_real (lo que cuenta Depósito al
-- recepcionar) — nunca los pisa. Es solo registro: no entra en ningún
-- cálculo (costeo, precios, Recepción). Depósito no lo ve — en la
-- pantalla de Recepción se sigue prellenando con cantidad_cajones, como
-- hoy.
--
-- Sin default a nivel de columna: si se deja vacío al marcar "Retirado",
-- queda NULL y se interpreta como "se retiró todo lo cargado" — no hace
-- falta prellenarlo con cantidad_cajones para lograr ese comportamiento
-- (el campo arranca vacío en la pantalla, a propósito).
--
-- Cambio aditivo: no afecta ninguna fila existente, no hace falta
-- backfill. Seguro de correr más de una vez.

alter table compras add column if not exists cantidad_cajones_retirada numeric;

comment on column compras.cantidad_cajones_retirada is 'Cajones que Logística anotó como efectivamente retirados del puesto (opcional, solo cajones — nunca kilos). Registro aparte: nunca pisa cantidad_cajones ni cantidad_cajones_real, y no entra en ningún cálculo (costeo, precios, Recepción). NULL = no se anotó nada, se asume que se retiró todo lo cargado.';
