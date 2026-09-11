-- BLOQUE D de 4: la coherencia, en las DOS direcciones.
-- Ver compra_en_caja_nuestra_2a_columna_y_candado.sql para el por que.
-- DEPENDE DEL BLOQUE A: sin la columna, aborta.
--
-- Con `=` y no con un `if`: un CHECK que cubre un solo lado deja pasar el
-- espejo en silencio. Paso con pedidos_renglones, que prohibia "ficha sin
-- articulo" y permitia justo lo contrario — nueve dias de pedidos con la
-- ficha en NULL y ni un error.
--
-- Las dos direcciones que cierra:
--   en_origen sin compra  -> una guia que dice venir de una compra y no dice
--                            de cual: el candado unico no la agarra (NULL no
--                            choca con nada) y queda fuera de toda trazabilidad.
--   compra sin en_origen  -> una guia normal con una compra colgada, que el
--                            candado SI cuenta: bloquearia la guia en origen
--                            verdadera de esa compra, y el error no diria por que.
--
-- Mismo molde que reprocesos_consumos_compra_coherente, que ya esta en el
-- esquema con esta forma.
do $$
begin
  if to_regclass('public.reprocesos') is null then
    raise exception 'no existe la tabla reprocesos: base equivocada';
  end if;
  if not exists (select 1 from information_schema.columns
                 where table_schema = 'public' and table_name = 'reprocesos'
                   and column_name = 'compra_origen_id') then
    raise exception 'falta compra_origen_id: corre el bloque A primero';
  end if;

  alter table reprocesos drop constraint if exists reprocesos_compra_origen_coherente;
  alter table reprocesos add constraint reprocesos_compra_origen_coherente
    check ((tipo = 'en_origen') = (compra_origen_id is not null));
end $$;
