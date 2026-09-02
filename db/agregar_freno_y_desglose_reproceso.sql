-- ETAPA 2 DE "ELEGIR DEL STOCK QUE HAY": el freno del reproceso y su
-- desglose editable. Las dos piezas van juntas y por eso comparten migración.
--
-- TODO EN UN ÚNICO do $$ ... end $$: el editor SQL de Supabase confirma cada
-- sentencia por su cuenta, así que un script de varias sentencias puede
-- aplicarse a medias. Adentro de un bloque do sí es todo-o-nada de verdad.
-- Idempotente: se puede correr dos veces sin romper nada.
-- ADITIVA: no toca ninguna fila existente.
--
-- QUÉ AGREGA
--
-- 1. `operarios_deposito`: la lista corta del depósito, editable desde
--    Administración igual que los catálogos del puesto. Va con SELECTOR y no
--    con texto libre porque en una pantalla que se usa apurado el texto libre
--    termina en "juan", "Juan", "jaun" y vacíos — y ahí contar por operario
--    deja de contar nada. El índice único es sobre el nombre NORMALIZADO
--    (minúsculas y sin espacios de más): esa es la regla que impide que la
--    misma persona entre dos veces.
--
-- 2. Tres columnas en `reprocesos`:
--
--    consumos_editados     El operario corrigió el reparto que propuso el
--                          server. Sin esto, un consumo declarado a mano
--                          queda indistinguible de uno derivado por FIFO — el
--                          mismo error que cargar los saldos iniciales de
--                          Vacíos como 'ajuste'. Va POR GUÍA y no por
--                          consumo: lo que hay que poder contestar es "¿este
--                          reparto lo dijo una persona?", no cuál renglón tocó.
--
--    excepcion_motivo      Por qué se cargó pese al freno. NULL = no hubo
--                          excepción. El motivo ES la marca: un booleano
--                          aparte podría contradecirlo, y entonces habría que
--                          decidir a cuál creerle.
--
--    excepcion_operario_id Quién la usó, contra la lista. FK sin ON DELETE:
--                          un operario con excepciones cargadas no se puede
--                          borrar, y por eso la lista se da de baja con
--                          `activo` en vez de borrarse.

do $$
begin
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
    -- 2. Las tres columnas de reprocesos.
    -- ---------------------------------------------------------------------
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'reprocesos' and column_name = 'consumos_editados'
    ) then
        alter table reprocesos
            add column consumos_editados boolean not null default false;
    end if;

    if not exists (
        select 1 from information_schema.columns
        where table_name = 'reprocesos' and column_name = 'excepcion_motivo'
    ) then
        alter table reprocesos add column excepcion_motivo text;
    end if;

    if not exists (
        select 1 from information_schema.columns
        where table_name = 'reprocesos' and column_name = 'excepcion_operario_id'
    ) then
        alter table reprocesos
            add column excepcion_operario_id bigint references operarios_deposito (id);
    end if;

    -- Los dos datos de la excepción viajan juntos, y el motivo no puede ser
    -- una cadena vacía: "se cargó igual" sin motivo no es una excepción, es un
    -- pase libre.
    --
    -- Los "is not null" del segundo brazo NO son redundantes: en Postgres un
    -- check que evalúa a NULL SE DA POR CUMPLIDO. Sin ellos, con el operario
    -- en NULL el brazo daba "true and null" = null, y una guía con motivo y
    -- sin quién entraba igual. Se descubrió PROBANDO que el check rechaza, no
    -- leyendo que existe.
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

    -- Contar las excepciones por operario y por día sin recorrer la tabla
    -- entera. Parcial: las guías sin excepción —que son casi todas— no entran.
    if not exists (select 1 from pg_class where relname = 'reprocesos_excepcion_idx') then
        create index reprocesos_excepcion_idx
            on reprocesos (fecha_operacion, excepcion_operario_id)
            where excepcion_motivo is not null;
    end if;

    -- ---------------------------------------------------------------------
    -- 3. Los comentarios, que son parte del dato.
    -- ---------------------------------------------------------------------
    comment on table operarios_deposito is
        'La lista corta del depósito, para el selector de la excepción al freno del reproceso. Editable desde Administración, igual que los catálogos del puesto. Se da de BAJA con activo, nunca se borra: una excepción cargada apunta acá.';
    comment on column operarios_deposito.activo is
        'false = ya no aparece en el selector, pero sus excepciones viejas siguen contando. El nombre es único normalizado (minúsculas, sin espacios de más).';
    comment on column reprocesos.consumos_editados is
        'El operario corrigió el reparto por lote que propuso el server. false = el reparto es el que salió del FIFO. Va por guía y no por consumo: lo que hay que poder contestar es si el reparto lo declaró una persona, no qué renglón tocó.';
    comment on column reprocesos.excepcion_motivo is
        'Por qué se cargó esta guía pese al freno (no había remanente a la fecha). NULL = no hubo excepción: el motivo ES la marca, para que no haya un booleano que pueda contradecirlo.';
    comment on column reprocesos.excepcion_operario_id is
        'Quién usó la excepción, elegido de operarios_deposito. Selector y no texto libre: con texto libre la misma persona entra como "juan", "Juan" y "jaun", y contar por operario deja de contar nada.';
end $$;
