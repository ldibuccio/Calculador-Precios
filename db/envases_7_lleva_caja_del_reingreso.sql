do $$
begin
  if not exists (select 1 from information_schema.columns
                  where table_name = 'movimientos_stock'
                    and column_name = 'lleva_caja_nuestra') then
    alter table movimientos_stock add column lleva_caja_nuestra boolean;
  end if;

  alter table movimientos_stock
    drop constraint if exists movimientos_stock_lleva_caja_solo_reproceso;
  alter table movimientos_stock
    add constraint movimientos_stock_lleva_caja_solo_reproceso
    check (lleva_caja_nuestra is null
           or destino_rechazo is not distinct from 'reproceso');

  alter table movimientos_stock
    drop constraint if exists movimientos_stock_envase_coherente;
  alter table movimientos_stock
    add constraint movimientos_stock_envase_coherente
    check ((lleva_caja_nuestra is true) = (envase_id is not null));

  if (select count(*) from pg_constraint
       where conname in ('movimientos_stock_lleva_caja_solo_reproceso',
                         'movimientos_stock_envase_coherente')) <> 2 then
    raise exception 'movimientos_stock quedo sin las guardas de la caja del reingreso';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 7. CORRE SOLO. Verificacion aparte (envases_8).
--
-- SON DOS COLUMNAS Y NO UN envase_id NULEABLE, igual que en reprocesos: ese
-- NULL tiene DOS significados y los dos llegan igual a la cuenta de cajas.
--     true  + envase  -> libera una caja de ese tipo
--     false + NULL    -> no volvio en caja nuestra (envase perdido, o el
--                        cajon vino chico): un cero VERDADERO
--     NULL  + NULL    -> reingreso anterior a estas columnas, sin declarar:
--                        NO es "no libero", es "no sabemos"
--
-- Sin la segunda columna, el que contesta "no volvio en caja nuestra" queda
-- indistinguible del reingreso viejo que nadie declaro, y el hueco no se
-- puede contar ni mostrar. Es el mismo argumento escrito en el comentario
-- de reprocesos.envase_id, y la misma forma de las dos guardas: una por
-- destino y una de coherencia en las DOS direcciones, porque una que
-- cubriera un solo lado deja pasar el espejo en silencio.
--
-- `is not distinct from` y no `=`: con destino_rechazo en NULL la
-- comparacion da NULL y un CHECK que evalua NULL PASA (corolario 67).
