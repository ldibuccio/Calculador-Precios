-- ============================================================================
-- MUDANZA DE BASE, PASO 1 de 4: enganchar la base VIEJA desde la NUEVA
-- ============================================================================
-- Se corre UNA vez, en el SQL Editor de la base NUEVA (la del proyecto nuevo,
-- el que está en la región que querés). Deja la base vieja visible como el
-- esquema "origen", de solo lectura, para poder copiar en el paso 2.
--
-- ANTES DE CORRER ESTO, la base nueva tiene que tener el esquema creado:
-- correr db/esquema_completo.sql entero, una sola vez.
--
-- QUÉ COMPLETAR ABAJO (dos cosas, las dos del proyecto VIEJO):
--   HOST_VIEJO  — Dashboard del proyecto viejo -> Connect. Usá el host de
--                 "Session pooler" (aws-N-<region>.pooler.supabase.com), NO el
--                 directo: el directo es IPv6 y la conexión puede no salir. El
--                 usuario del pooler tiene forma postgres.<ref-del-proyecto>.
--   CLAVE_VIEJA — la contraseña de la base del proyecto viejo.
--
-- SOBRE LA CONTRASEÑA: queda escrita acá y en el historial del SQL Editor.
-- El paso 4 borra el enganche, y en el checklist está anotado ROTAR esa
-- contraseña cuando termine la mudanza. No la dejes viva.
--
-- Es idempotente: se puede correr de nuevo sin romper nada (borra el enganche
-- anterior y lo rehace).
-- ============================================================================

drop schema if exists origen cascade;
drop server if exists base_vieja cascade;

create extension if not exists postgres_fdw;

create server base_vieja
    foreign data wrapper postgres_fdw
    options (
        host 'HOST_VIEJO',
        port '5432',
        dbname 'postgres',
        sslmode 'require',
        -- Sin esto, una tabla grande se trae fila por fila y tarda una eternidad.
        fetch_size '10000'
    );

create user mapping for current_user
    server base_vieja
    options (user 'USUARIO_VIEJO', password 'CLAVE_VIEJA');

create schema origen;

-- Trae las 40 tablas de la base vieja como tablas foráneas de solo lectura.
import foreign schema public from server base_vieja into origen;

-- ----------------------------------------------------------------------------
-- Comprobación: tiene que decir 40, y los conteos tienen que ser los de la
-- base vieja. Si esto anda, el enganche está bien y podés ir al paso 2.
-- ----------------------------------------------------------------------------
select count(*) as tablas_enganchadas from information_schema.foreign_tables;

select 'articulos' as tabla, count(*) from origen.articulos
union all select 'clientes', count(*) from origen.clientes
union all select 'compras', count(*) from origen.compras
union all select 'pedidos_renglones', count(*) from origen.pedidos_renglones
union all select 'precios_venta_historial', count(*) from origen.precios_venta_historial;
