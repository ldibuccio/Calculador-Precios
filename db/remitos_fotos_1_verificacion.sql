select 'remitos_fotos_1_quien' as que_migracion,
  (select count(*) from information_schema.columns
    where table_name = 'remitos_fotos' and column_name = 'cargada_por'
      and is_nullable = 'NO') as columna,
  (select count(*) from pg_constraint
    where conname = 'remitos_fotos_cargada_por_check') as checks,
  count(*) as fotos,
  count(*) filter (where cargada_por = 'administracion') as de_administracion,
  (select count(*) from remitos where recibido_el is not null) as remitos_recibidos
from remitos_fotos;

-- Se corre DESPUES del bloque, aparte. columna 1 · checks 1 · y
-- de_administracion igual a fotos (todas entraron por Recibir).
