do $$
begin
  if not exists (select 1 from information_schema.columns
                  where table_name = 'reprocesos' and column_name = 'envase_id') then
    alter table reprocesos add column envase_id bigint references envases (id);
  end if;

  if not exists (select 1 from information_schema.columns
                  where table_name = 'reprocesos' and column_name = 'lleva_caja_nuestra') then
    alter table reprocesos add column lleva_caja_nuestra boolean;
  end if;

  alter table reprocesos drop constraint if exists reprocesos_envase_coherente;
  alter table reprocesos add constraint reprocesos_envase_coherente
    check ((lleva_caja_nuestra is true) = (envase_id is not null));

  if not exists (select 1 from pg_constraint
                  where conname = 'reprocesos_envase_coherente') then
    raise exception 'reprocesos quedo sin la guarda de coherencia del envase';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 3 de 5. CORRE SOLO. Verificacion aparte (envases_6).
--
-- La guia R pasa a decir EN QUE CAJA se armo. Lo ESCRIBE siempre el server
-- —copiado de la ficha cuando el envase es fijo— y la pantalla lo PREGUNTA
-- solo cuando la ficha es de envase variable (mango, cherry). Guardarlo
-- solo en las variables dejaria el conteo de cajas de las fijas leyendose
-- de la ficha de HOY, y el dia que alguien le cambie el envase a una ficha
-- se re-etiqueta la historia en silencio: es lo mismo que nos negamos a
-- hacer con unidad_compra.
--
-- `lleva_caja_nuestra` es COLUMNA APARTE y no un envase_id en NULL, porque
-- ese NULL tendria dos significados (descartable / guia vieja) y los dos
-- llegan igual a la cuenta. Los tres estados:
--     true  + envase   -> consume una caja de ese tipo por bulto de primera
--     false + NULL     -> descartable: el cajon vino chico, no lleva caja
--     NULL  + NULL     -> guia anterior a esta columna, sin declarar
--
-- El CHECK los fija en LAS DOS DIRECCIONES: `(lleva is true) = (envase is
-- not null)`. Uno que cubriera un solo lado dejaria pasar el espejo.
