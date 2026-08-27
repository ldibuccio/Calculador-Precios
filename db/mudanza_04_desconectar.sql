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

-- Tiene que devolver 0 filas las tres.
select count(*) as servidores_foraneos from pg_foreign_server;
select count(*) as tablas_foraneas from information_schema.foreign_tables;
select count(*) as extension_fdw from pg_extension where extname = 'postgres_fdw';
