select 'comparar_esquema' as que_consulta,
       count(*) over () as tablas_total,
       t.relname as tabla,
       count(a.attnum) as columnas,
       md5(string_agg(a.attname || ':' || format_type(a.atttypid, a.atttypmod) || ':'
             || a.attnotnull::text, ',' order by a.attname)) as huella,
       max(s.n_live_tup) as filas_aprox
from pg_class t
join pg_namespace n on n.oid = t.relnamespace and n.nspname = 'public'
join pg_attribute a on a.attrelid = t.oid and a.attnum > 0 and not a.attisdropped
left join pg_stat_user_tables s on s.relid = t.oid
where t.relkind = 'r'
group by t.relname
order by t.relname;

-- Compara el esquema de una base contra el del repo sin copiar nada: una fila
-- por tabla, con la cantidad de columnas y una huella de sus nombres, tipos y
-- NOT NULL. Se corre en las dos bases y contra una base cargada con
-- db/esquema_completo.sql, y se comparan las filas. No mira defaults,
-- CHECKs, FKs ni índices: dos huellas iguales dicen que las COLUMNAS son las
-- mismas, no que la tabla sea idéntica. filas_aprox sale de las estadísticas
-- de Postgres, así que es aproximado.
--
-- Corrida el 28/09: las 64 tablas compartidas dan la misma huella que el
-- repo; Frutamax tiene 8 de más y a Palmala le falta
-- corte_respaldo_fichas_reprocesos (ver db/corridas_confirmadas.md).
