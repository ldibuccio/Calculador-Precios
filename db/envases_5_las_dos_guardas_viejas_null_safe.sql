do $$
declare
  ofensores integer;
begin
  select count(*) into ofensores from movimientos_stock
   where (proveedor_devolucion_id is not null or compra_devolucion_id is not null)
     and destino_rechazo is distinct from 'devolucion_proveedor';
  if ofensores > 0 then
    raise exception 'hay % filas que la guarda corregida rechazaria: revisalas antes', ofensores;
  end if;

  alter table movimientos_stock drop constraint if exists movimientos_stock_proveedor_solo_devolucion;
  alter table movimientos_stock add constraint movimientos_stock_proveedor_solo_devolucion
    check (proveedor_devolucion_id is null
           or destino_rechazo is not distinct from 'devolucion_proveedor');

  alter table movimientos_stock drop constraint if exists movimientos_stock_compra_solo_devolucion;
  alter table movimientos_stock add constraint movimientos_stock_compra_solo_devolucion
    check (compra_devolucion_id is null
           or destino_rechazo is not distinct from 'devolucion_proveedor');
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 5 de 5, y es SEPARABLE: no lo necesita el stock de cajas. Corregi
-- estas dos porque son la MISMA forma que el CHECK del bloque 4 y salieron
-- al probarlo (buscar la otra copia es obligatorio).
--
-- El agujero, medido y no deducido: con `destino_rechazo` en NULL,
-- `destino_rechazo = 'devolucion_proveedor'` da NULL, y un CHECK que evalua
-- NULL PASA. O sea que una MERMA con proveedor_devolucion_id entraba, y una
-- con compra_devolucion_id tambien. Verificado contra el esquema real:
--     merma con proveedor_devolucion_id   ->  ENTRA   (antes)
--     merma con proveedor_devolucion_id   ->  RECHAZA (despues)
--     devolucion legitima, de control     ->  ENTRA   (las dos veces)
--
-- No es un bug vivo: hoy el unico que escribe esas columnas es la ruta del
-- reingreso, que siempre pone un destino. Es una guarda que dice algo que
-- no cumple, y eso se cobra el dia que aparezca un segundo escritor.
--
-- El bloque ABORTA si encuentra filas que la guarda corregida rechazaria,
-- en vez de fallar al crear el constraint con un mensaje de Postgres que no
-- dice cuantas son. `ofensores_viejos` lo cuenta en la verificacion.
