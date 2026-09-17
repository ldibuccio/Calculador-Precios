do $$
begin
  alter table movimientos_stock drop column if exists envase_id;
  alter table movimientos_stock drop column if exists lleva_caja_nuestra;

  if exists (select 1 from information_schema.columns
              where table_name = 'movimientos_stock'
                and column_name in ('envase_id', 'lleva_caja_nuestra')) then
    raise exception 'movimientos_stock quedo con la caja del reingreso';
  end if;

  if (select count(*) from pg_constraint
       where conname in ('movimientos_stock_envase_solo_reproceso',
                         'movimientos_stock_lleva_caja_solo_reproceso',
                         'movimientos_stock_envase_coherente')) <> 0 then
    raise exception 'quedo alguna guarda de la caja del reingreso';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 9. CORRE SOLO. Y envases_10 se corre DOS veces: antes (es la unica
-- forma de ver cuantas filas tenian la columna escrita) y despues.
--
-- DESHACE los bloques 4 y 7. Su premisa era que el rechazo con destino
-- 'reproceso' LIBERA la caja. Es falsa, y la corrigio el dueno el 17/09: LA
-- CAJA SE TIRA. No hay nada que devolverle al stock, y la pata `liberadas`
-- sumaba algo que no ocurre.
--
-- Esa caja NO se pierde de las cuentas: se descuenta cuando la guia R la
-- armo, y su costo va adentro de `rechazos_perdidos`. Lo que se saca no es un
-- dato: es un dato que decia lo contrario de lo que pasa.
--
-- Y HAY UNA SEGUNDA RAZON, medida contra db/esquema_completo.sql con los
-- cuatro casos corridos: el codigo escribe `envase_id` y NUNCA escribio
-- `lleva_caja_nuestra`, asi que con el bloque 7 puesto el CHECK de coherencia
-- RECHAZA el reingreso a 'reproceso' de toda ficha con envase derivable.
--
--   A) como lo escribe el codigo hoy ... RECHAZA <- ..._envase_coherente
--   B) control, con las DOS columnas ... ENTRA
--   C) control, una merma comun ........ ENTRA
--   D) el rechazo a STOCK .............. ENTRA
--
-- `if exists` y no `if not exists`: esto borra ESTRUCTURA. El bloque 7 puede
-- no haberse corrido nunca, y el drop tiene que pasar igual.
--
-- EL CODIGO VA PRIMERO, al reves de lo habitual: `liberadas` LEE esa columna,
-- asi que correr esto con el codigo viejo desplegado rompe la pantalla de
-- Cajas. Sin la pata, el codigo anda con la columna y sin ella.
