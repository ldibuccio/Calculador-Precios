do $$
begin
  if not exists (select 1 from information_schema.columns
                  where table_name = 'movimientos_stock' and column_name = 'envase_id') then
    alter table movimientos_stock add column envase_id bigint references envases (id);
  end if;

  alter table movimientos_stock drop constraint if exists movimientos_stock_envase_solo_reproceso;
  alter table movimientos_stock add constraint movimientos_stock_envase_solo_reproceso
    check (envase_id is null
           or destino_rechazo is not distinct from 'reproceso');

  if not exists (select 1 from pg_constraint
                  where conname = 'movimientos_stock_envase_solo_reproceso') then
    raise exception 'movimientos_stock quedo sin la guarda del envase liberado';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 4 de 5. CORRE SOLO. Verificacion aparte (envases_6).
--
-- El rechazo con destino 'reproceso' VACIA nuestra caja: la mercaderia
-- vuelve a cajon grande y la caja queda libre. Es la unica de las cuatro
-- puertas del rechazo que suma al stock de cajas.
--
-- Con ficha de envase fijo el envase se deriva de la ficha; con ficha
-- VARIABLE no se puede, asi que la pantalla lo pregunta y el server lo
-- escribe siempre — mismo criterio que en la guia R.
--
-- `is not distinct from` Y NO `=`, y no es estilo: con destino_rechazo en
-- NULL, `destino_rechazo = 'reproceso'` da NULL, y un CHECK que evalua NULL
-- PASA. Medido: con `=` una merma con envase_id entraba. Las dos guardas
-- viejas de esta tabla tienen el mismo agujero y las corrige el bloque 5.
