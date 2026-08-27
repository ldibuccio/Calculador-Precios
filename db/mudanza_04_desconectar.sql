-- ============================================================================
-- MUDANZA DE BASE, PASO 4 de 4: desenganchar la base vieja
-- ============================================================================
-- Se corre en el SQL Editor de la base NUEVA, cuando la mudanza terminó y
-- Railway ya apunta a la nueva y anda bien.
--
-- POR QUÉ IMPORTA: el user mapping del paso 1 guarda la CONTRASEÑA de la base
-- vieja adentro de la base nueva. Dejarlo vivo es dejar una puerta abierta de
-- una base a la otra, con credencial incluida. Esto lo borra.
--
-- NO lo corras antes de tiempo: mientras el enganche exista podés volver a
-- correr el paso 2 para traer lo que se haya cargado en la vieja mientras
-- tanto. Desenganchá recién cuando ya no vayas a copiar más.
--
-- DESPUÉS DE ESTO, EN EL DASHBOARD DEL PROYECTO VIEJO: rotar la contraseña de
-- la base. Quedó escrita en el historial del SQL Editor de la base nueva.
-- ============================================================================

drop schema if exists origen cascade;
drop server if exists base_vieja cascade;
drop extension if exists postgres_fdw;

-- Los tres controles en UNA consulta: el SQL Editor de Supabase muestra
-- solamente el resultado de la última, así que tres consultas sueltas
-- dejarían dos invisibles. Tiene que dar 0 | 0 | 0.
select (select count(*) from pg_foreign_server)                                  as servidores,
       (select count(*) from information_schema.foreign_tables)                  as tablas_foraneas,
       (select count(*) from pg_extension where extname = 'postgres_fdw')        as extension;
