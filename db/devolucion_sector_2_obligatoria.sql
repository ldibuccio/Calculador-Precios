do $$
begin
  if to_regclass('movimientos_stock') is null or not exists (
       select 1 from information_schema.columns
        where table_name = 'movimientos_stock' and column_name = 'cargada_desde') then
    raise exception 'falta la columna: corre primero devolucion_sector_1';
  end if;
  if exists (select 1 from pg_constraint
              where conname = 'movimientos_stock_devolucion_con_sector') then
    raise exception 'el check ya existe: este bloque ya corrio';
  end if;
  update movimientos_stock set cargada_desde = 'deposito'
   where tipo = 'devolucion_deposito' and cargada_desde is null;
  alter table movimientos_stock add constraint movimientos_stock_devolucion_con_sector
    check ((tipo = 'devolucion_deposito') = (cargada_desde is not null));
end $$;

-- DEVOLVER MERCADERIA DESDE ADMINISTRACION, bloque 2 de 2.
--
-- Se corre DESPUES del deploy (corolario 94): desde ahi toda devolucion
-- dice su sector, y solo la devolucion lo lleva. Primero marca 'deposito'
-- en las que el codigo viejo haya cargado entre el bloque 1 y el deploy:
-- en esa ventana Administracion todavia no tenia el boton.
