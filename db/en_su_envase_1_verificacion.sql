select 'en_su_envase_1_renglon' as que_migracion,
  (select count(*) from information_schema.columns
    where table_name = 'pedidos_renglones' and column_name = 'en_su_envase'
      and is_nullable = 'NO') as columna,
  (select count(*) from pg_constraint
    where conname = 'pedidos_renglones_en_su_envase_solo_armado') as checks,
  count(*) filter (where r.en_su_envase) as en_su_envase,
  count(*) filter (where r.armado_el is not null and f.envase_variable) as armados_envase_variable,
  count(*) as renglones
from pedidos_renglones r
left join fichas_logistica f on f.id = r.ficha_id;

-- Se corre DESPUES del bloque, aparte. columna 1 · checks 1 ·
-- en_su_envase 0 (lo de antes queda como estaba).
