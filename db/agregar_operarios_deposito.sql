-- ############################################################################
-- ATENCIÓN — NO REUSAR. LO QUE CREA ESTE SCRIPT SE BORRÓ EL 02/09/2026.
--
-- `operarios_deposito` y `excepcion_operario_id` existían para la salida de
-- escape del freno del reproceso, que se descartó: el reproceso es 100% o
-- nada. Los borró db/sacar_excepcion_del_freno.sql.
--
-- Queda como registro de lo que se corrió el 01/09. Correrlo de nuevo
-- volvería a crear una tabla que ningún código usa.
-- ############################################################################

-- ARRASTRE DE LA ETAPA 2: el operario de la excepción pasa de TEXTO LIBRE a
-- SELECTOR contra una lista.
--
-- POR QUÉ HAY DOS MIGRACIONES Y NO UNA: la primera versión
-- (`agregar_freno_y_desglose_reproceso.sql`, corrida el 01/09 en las dos
-- bases) guardaba el nombre del operario como texto libre. La decisión del
-- selector llegó después, y en una pantalla que se usa apurado el texto libre
-- termina en "juan", "Juan", "jaun" y vacíos — y ahí contar por operario deja
-- de contar nada.
--
-- SE PUEDE CORRER EN CUALQUIERA DE LOS DOS ESTADOS: sobre una base con la
-- versión de texto (la convierte) o sobre una que ya tenga el selector (no
-- hace nada). Idempotente.
--
-- SI HUBIERA EXCEPCIONES YA CARGADAS CON NOMBRE DE TEXTO, el bloque se corta
-- sin tocar nada: convertirlas a mano es decisión de una persona, no de un
-- script. Al 01/09 no hay ninguna en ninguna de las dos bases (0 guías con
-- excepción en Frutamax y en Palmala), así que no debería saltar.

do $$
declare
    con_texto int := 0;
begin
    -- ---------------------------------------------------------------------
    -- GUARDA: no perder nombres ya cargados.
    -- ---------------------------------------------------------------------
    if exists (
        select 1 from information_schema.columns
        where table_name = 'reprocesos' and column_name = 'excepcion_operario'
    ) then
        execute 'select count(*) from reprocesos where excepcion_operario is not null'
            into con_texto;
        if con_texto > 0 then
            raise exception
                'Hay % excepciones con el operario cargado como texto. Convertirlas a la lista es decisión de una persona: no las toca este script.',
                con_texto;
        end if;
    end if;

    -- ---------------------------------------------------------------------
    -- 1. La lista del depósito.
    -- ---------------------------------------------------------------------
    if not exists (select 1 from pg_class where relname = 'operarios_deposito') then
        create table operarios_deposito (
            id        bigint generated always as identity primary key,
            nombre    text not null check (btrim(nombre) <> ''),
            activo    boolean not null default true,
            creado_en timestamptz not null default now()
        );
    end if;

    -- El nombre NORMALIZADO es lo único: "Juan", "juan" y " Juan " son la
    -- misma persona, y si entran como tres, contar por operario no cuenta nada.
    if not exists (select 1 from pg_class where relname = 'operarios_deposito_nombre_unico') then
        create unique index operarios_deposito_nombre_unico
            on operarios_deposito (lower(btrim(nombre)));
    end if;

    -- ---------------------------------------------------------------------
    -- 2. La columna nueva, la vieja afuera.
    -- ---------------------------------------------------------------------
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'reprocesos' and column_name = 'excepcion_operario_id'
    ) then
        alter table reprocesos
            add column excepcion_operario_id bigint references operarios_deposito (id);
    end if;

    -- El check y el índice nombran la columna vieja: se rehacen ANTES de
    -- soltarla, o el drop se lleva puesto lo que dependa de ella.
    if exists (
        select 1 from pg_constraint
        where conrelid = 'reprocesos'::regclass and conname = 'reprocesos_excepcion_completa'
    ) then
        alter table reprocesos drop constraint reprocesos_excepcion_completa;
    end if;
    alter table reprocesos
        add constraint reprocesos_excepcion_completa
        check (
            (excepcion_motivo is null and excepcion_operario_id is null)
            or (excepcion_motivo is not null and excepcion_operario_id is not null
                and btrim(excepcion_motivo) <> '')
        );

    if exists (select 1 from pg_class where relname = 'reprocesos_excepcion_idx') then
        drop index reprocesos_excepcion_idx;
    end if;
    create index reprocesos_excepcion_idx
        on reprocesos (fecha_operacion, excepcion_operario_id)
        where excepcion_motivo is not null;

    if exists (
        select 1 from information_schema.columns
        where table_name = 'reprocesos' and column_name = 'excepcion_operario'
    ) then
        alter table reprocesos drop column excepcion_operario;
    end if;

    -- ---------------------------------------------------------------------
    -- 3. Los comentarios, que son parte del dato.
    -- ---------------------------------------------------------------------
    comment on table operarios_deposito is
        'La lista corta del depósito, para el selector de la excepción al freno del reproceso. Editable desde Administración, igual que los catálogos del puesto. Se da de BAJA con activo, nunca se borra: una excepción cargada apunta acá.';
    comment on column operarios_deposito.activo is
        'false = ya no aparece en el selector, pero sus excepciones viejas siguen contando. El nombre es único normalizado (minúsculas, sin espacios de más).';
    comment on column reprocesos.excepcion_operario_id is
        'Quién usó la excepción, elegido de operarios_deposito. Selector y no texto libre: con texto libre la misma persona entra como "juan", "Juan" y "jaun", y contar por operario deja de contar nada.';
end $$;
