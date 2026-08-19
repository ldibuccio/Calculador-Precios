-- ============================================================================
-- Los envases dejan de pertenecer a un cliente: catálogo único compartido.
--
-- Motivo: una "caja mediana" que usan Día y Coto era dos filas con dos
-- costos a mantener. Ahora es UNA fila con UN costo, y cada ficha
-- logística elige el envase que corresponda. Si un envase es exclusivo de
-- un cliente (ej. caja impresa con su marca), se distingue por el NOMBRE.
--
-- Correr en LAS DOS bases (Frutamax y Palmala), DESPUÉS del deploy del
-- código que ya no usa envases.cliente_id (si se corre antes, la app viva
-- se rompe). Registrar cada base en db/APLICADO.md.
--
-- ANTES de tocar nada, correr la CONSULTA PREVIA (solo lectura) para ver
-- qué hay. Los envases existentes quedan tal cual, con su historial de
-- costos intacto — envases_costo_historial no se toca.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- CONSULTA PREVIA (solo lectura): los envases con su cliente actual y su
-- costo vigente. Correr en las dos bases y mirar antes de migrar.
-- ---------------------------------------------------------------------------
-- select e.id, e.nombre, c.nombre as cliente_actual, e.activo,
--        h.costo as costo_vigente, h.vigente_desde
-- from envases e
-- left join clientes c on c.id = e.cliente_id
-- left join lateral (
--     select costo, vigente_desde from envases_costo_historial
--     where envase_id = e.id and vigente_desde <= current_date
--     order by vigente_desde desc limit 1
-- ) h on true
-- order by e.nombre;

-- ---------------------------------------------------------------------------
-- MIGRACIÓN. El primer bloque chequea nombres duplicados entre clientes
-- distintos: si los hay, corta ANTES de tocar nada, con la lista de los
-- nombres en conflicto — hay que renombrarlos a mano primero (el nombre
-- pasa a ser único global).
-- ---------------------------------------------------------------------------
begin;

do $$
declare
    duplicados text;
begin
    select string_agg(nombre, ', ')
    into duplicados
    from (select nombre from envases group by nombre having count(*) > 1) t;

    if duplicados is not null then
        raise exception 'Hay envases con el mismo nombre para clientes distintos: %. Renombralos primero — el nombre pasa a ser único.', duplicados;
    end if;
end $$;

-- El envase deja de pertenecer a un cliente. Al borrar la columna caen
-- solos la FK a clientes y el UNIQUE (cliente_id, nombre) que la incluían.
alter table envases drop column if exists cliente_id;

-- El nombre pasa a ser único global (antes era único por cliente).
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'envases_nombre_key') then
        alter table envases add constraint envases_nombre_key unique (nombre);
    end if;
end $$;

commit;

-- Después de correr esto en LAS DOS bases: correr la CONSULTA 1 de
-- db/verificar_esquema.sql en las dos y comparar — las firmas de "envases"
-- cambian con esta migración y tienen que volver a coincidir entre sí.
