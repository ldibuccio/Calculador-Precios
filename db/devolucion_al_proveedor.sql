-- CUARTO DESTINO DEL RECHAZO: se le devuelve al proveedor.
--
-- La mercadería que el supermercado rechazó vuelve al proveedor que la
-- trajo y NO se le paga. Sale del stock, no entra al pool de segunda, y su
-- costo no es ni venta ni pérdida: la operación no ocurrió.
--
-- El descuento al proveedor se arregla fuera del sistema (11/09): acá no
-- hay cuenta corriente. Lo único que se guarda es A QUIÉN se le devolvió.
--
-- UN SOLO `do $$` porque los tres pasos son todo-o-nada: con la columna
-- puesta y el CHECK viejo, la pantalla guardaría y la base rechazaría.
--
-- OJO CON EL `if not exists`: va SOLO en la columna, que es ESTRUCTURA.
-- Para el CHECK —que es CONTENIDO, una lista de valores— se DROPEA Y SE
-- RECREA siempre: un `if not exists` sobre una lista sale `DO` sin hacer
-- nada y deja la lista vieja adentro, que se ve igual que haber corrido
-- bien (regla del 09/09).
--
-- `movimientos_stock_segunda_segun_destino` NO se toca: su `else` ya exige
-- `bultos_segunda is null` para todo destino que no sea segunda/reproceso,
-- así que el valor nuevo ya queda bien. Verificado leyendo el constraint.

do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_name = 'movimientos_stock'
      and column_name = 'proveedor_devolucion_id'
  ) then
    alter table movimientos_stock
      add column proveedor_devolucion_id bigint references proveedores (id);
  end if;

  alter table movimientos_stock
    drop constraint if exists movimientos_stock_destino_rechazo_check;
  alter table movimientos_stock
    add constraint movimientos_stock_destino_rechazo_check
    check (destino_rechazo is null or destino_rechazo in
           ('stock', 'segunda', 'reproceso', 'devolucion_proveedor'));

  alter table movimientos_stock
    drop constraint if exists movimientos_stock_proveedor_solo_devolucion;
  alter table movimientos_stock
    add constraint movimientos_stock_proveedor_solo_devolucion
    check (proveedor_devolucion_id is null
           or destino_rechazo = 'devolucion_proveedor');
end $$;
