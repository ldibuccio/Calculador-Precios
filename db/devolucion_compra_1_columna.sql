-- DE QUE COMPRA salieron los bultos devueltos al proveedor.
--
-- El movimiento guarda `pedido_renglon_id` (de que renglon armado volvio) y
-- nada mas. La compra solo se alcanzaba rejugando el FIFO, y ahi hay un
-- problema que ninguna columna arregla sola: un renglon puede haberse
-- armado con DOS compras —25 bultos de una y 5 de otra— y de cuales 8
-- volvieron no lo sabe nadie. Nadie miro que caja venia de que cajon.
--
-- POR ESO LO ELIGE LA PERSONA AL CARGAR, y el sistema lo guarda: no inventa
-- el reparto, registra el declarado. Es el campo DIRECTO en vez del
-- derivado, y ya esta medido en este proyecto que el derivado miente en un
-- tercio de los casos justo donde mas se usa.
--
-- Y EL PROVEEDOR SALE DE LA COMPRA: los dos campos no pueden convivir. Con
-- la compra elegida, el proveedor se lee de ella; sin compra (una
-- devolucion vieja, o un reingreso sin renglon del que no se puede saber la
-- compra) queda el proveedor suelto, que es lo unico que se sabe. Escritos
-- los dos, serian la misma cosa dos veces y se pueden contradecir — que es
-- justo el agujero que esto viene a cerrar.
--
-- UN SOLO `do $$` porque es todo-o-nada: con la columna puesta y sin el
-- CHECK, la pantalla guardaria pares que la base tendria que rechazar.
--
-- El `if not exists` va SOLO en la columna, que es ESTRUCTURA. Los CHECK
-- son CONTENIDO —una condicion— y se DROPEAN y RECREAN siempre: un
-- `if not exists` sobre un CHECK sale `DO` sin hacer nada y deja la
-- condicion vieja adentro, que se ve igual que haber corrido bien.

do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_name = 'movimientos_stock'
      and column_name = 'compra_devolucion_id'
  ) then
    alter table movimientos_stock
      add column compra_devolucion_id bigint references compras (id);
  end if;

  alter table movimientos_stock
    drop constraint if exists movimientos_stock_compra_solo_devolucion;
  alter table movimientos_stock
    add constraint movimientos_stock_compra_solo_devolucion
    check (compra_devolucion_id is null
           or destino_rechazo = 'devolucion_proveedor');

  alter table movimientos_stock
    drop constraint if exists movimientos_stock_compra_o_proveedor;
  alter table movimientos_stock
    add constraint movimientos_stock_compra_o_proveedor
    check (compra_devolucion_id is null or proveedor_devolucion_id is null);
end $$;
