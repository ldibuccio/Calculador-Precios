-- ############################################################################
-- LA REGLA EN LA BASE: no se anula una recepción con la seña ya cobrada.
--
-- NO CORRER TODAVÍA. Primero hay que resolver la recepción 74 (vale emitido
-- el 07/09 y anulada el mismo día): mientras esa fila exista así, el bloque
-- aborta a propósito y no escribe nada. Es la guarda, no un error.
--
-- Por qué va igual en la base habiendo ya una guarda en Python: es la regla
-- de la casa —decide la base, el código traduce el error—. La guarda de
-- `anular_vacio_recibido` protege la app; esto protege también lo que se
-- escriba a mano en el editor, que es exactamente como se corrigen las cosas
-- acá.
--
-- `sena_anulada_el` NO entra: ahí se decidió no pagar, no hay plata.
-- ############################################################################
do $$
declare
  sucias int;
begin
  select count(*) into sucias from vacios_recibidos
  where anulado_el is not null
    and (sena_pagada_el is not null or sena_vale_el is not null);

  if sucias > 0 then
    raise exception
      'HAY % recepcion(es) anuladas con la seña ya cobrada. Resolvelas primero (ver db/vacios_anulados_con_plata.sql): el CHECK no se puede agregar con esas filas adentro.', sucias;
  end if;

  alter table vacios_recibidos
    add constraint vacios_recibidos_no_anular_cobrada
    check (anulado_el is null or (sena_pagada_el is null and sena_vale_el is null));

  comment on column vacios_recibidos.anulado_el is
    'NULL = movimiento vigente. Los movimientos nunca se borran físicamente: anular deja el registro visible como corrección y el stock lo excluye. NO se puede anular una recepción cuya seña ya se pagó o se cerró con vale (constraint vacios_recibidos_no_anular_cobrada): la plata ya salió de la caja, los cajones volverían a salir del stock, y la fila desaparecería de las dos listas de Señas, que filtran anulado_el IS NULL. sena_anulada_el sí deja anular: ahí se decidió no pagar.';
end $$;

select conname, pg_get_constraintdef(oid) definicion
from pg_constraint where conname = 'vacios_recibidos_no_anular_cobrada';
