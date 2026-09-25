do $$
declare
  r record;
begin
  if not exists (select 1 from pg_constraint where conname = 'guias_compra_dia_proveedor_origen') then
    raise exception 'falta el unique nuevo: corré primero guia_deposito_1';
  end if;

  for r in select conname from pg_constraint
            where conrelid = 'guias_compra'::regclass and contype = 'u'
              and conname <> 'guias_compra_dia_proveedor_origen' loop
    execute format('alter table guias_compra drop constraint %I', r.conname);
  end loop;
end $$;

-- SE CORRE DESPUÉS DEL DEPLOY del código que hace
-- `ON CONFLICT (fecha_operacion, proveedor_id, de_deposito)`. Antes rompe
-- toda carga de compra: el código viejo pregunta por el unique que esto borra.
--
-- Borra por CATÁLOGO y no por nombre: el viejo nació inline
-- (`unique (fecha_operacion, proveedor_id)`) y su nombre lo puso Postgres.
-- Deja exactamente el nuevo. Con el viejo puesto, el bloque 3 no puede crear
-- la guía de depósito de un día y proveedor que ya tiene la de Compras.
-- Se puede correr dos veces.
