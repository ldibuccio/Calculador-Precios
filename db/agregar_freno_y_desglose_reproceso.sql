-- ETAPA 2 DE "ELEGIR DEL STOCK QUE HAY": el freno del reproceso y su
-- desglose editable. Las dos piezas van juntas y por eso comparten migración.
--
-- TODO EN UN ÚNICO do $$ ... end $$: el editor SQL de Supabase confirma cada
-- sentencia por su cuenta, así que un script de varias sentencias puede
-- aplicarse a medias. Adentro de un bloque do sí es todo-o-nada de verdad.
-- Idempotente: se puede correr dos veces sin romper nada.
--
-- Tres columnas en `reprocesos`:
--
--   consumos_editados  El operario tocó el reparto que propuso el server.
--                      Sin esto, un consumo declarado a mano queda
--                      indistinguible de uno derivado por FIFO — el mismo
--                      error que ya cometimos cargando los saldos iniciales
--                      de Vacíos como 'ajuste'. Va POR GUÍA y no por
--                      consumo: lo que hay que poder contestar es "¿este
--                      reparto lo dijo una persona?", no cuál renglón tocó.
--
--   excepcion_motivo   Por qué se cargó pese al freno. NULL = no hubo
--                      excepción. El motivo ES la marca: un booleano aparte
--                      podría contradecirlo, y entonces habría que decidir a
--                      cuál creerle.
--
--   excepcion_operario Quién la usó. El sistema NO tiene identidad de
--                      operario (el acceso es una cookie firmada compartida,
--                      no un login por persona), así que el nombre se
--                      declara al cargar. Es débil como identidad y alcanza
--                      para lo que se pidió: que si alguien la usa siempre,
--                      se vea.
--
-- El check obliga a que los dos datos de la excepción viajen juntos: no hay
-- excepción sin motivo ni motivo sin quién.

do $$
begin
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
        where table_name = 'reprocesos' and column_name = 'excepcion_operario'
    ) then
        alter table reprocesos add column excepcion_operario text;
    end if;

    -- Los dos datos de la excepción viajan juntos, y ninguno puede ser una
    -- cadena vacía: "se cargó igual" sin motivo no es una excepción, es un
    -- pase libre.
    --
    -- Los "is not null" del segundo brazo NO son redundantes: en Postgres un
    -- check que evalúa a NULL SE DA POR CUMPLIDO. Sin ellos, con el operario
    -- en NULL el brazo daba "true and null" = null, y una guía con motivo y
    -- sin quién entraba igual. Se descubrió probando el check, no leyéndolo.
    if exists (
        select 1 from pg_constraint
        where conrelid = 'reprocesos'::regclass and conname = 'reprocesos_excepcion_completa'
    ) then
        alter table reprocesos drop constraint reprocesos_excepcion_completa;
    end if;
    alter table reprocesos
        add constraint reprocesos_excepcion_completa
        check (
            (excepcion_motivo is null and excepcion_operario is null)
            or (excepcion_motivo is not null and excepcion_operario is not null
                and btrim(excepcion_motivo) <> '' and btrim(excepcion_operario) <> '')
        );

    -- Contar las excepciones por operario y por día sin recorrer la tabla
    -- entera. Parcial: las guías sin excepción —que son casi todas— no
    -- entran al índice.
    if not exists (select 1 from pg_class where relname = 'reprocesos_excepcion_idx') then
        create index reprocesos_excepcion_idx
            on reprocesos (fecha_operacion, excepcion_operario)
            where excepcion_motivo is not null;
    end if;

    comment on column reprocesos.consumos_editados is
        'El operario corrigió el reparto por lote que propuso el server. false = el reparto es el que salió del FIFO. Va por guía y no por consumo: lo que hay que poder contestar es si el reparto lo declaró una persona, no qué renglón tocó.';
    comment on column reprocesos.excepcion_motivo is
        'Por qué se cargó esta guía pese al freno (no había remanente a la fecha). NULL = no hubo excepción: el motivo ES la marca, para que no haya un booleano que pueda contradecirlo.';
    comment on column reprocesos.excepcion_operario is
        'Quién usó la excepción, declarado al cargar. El sistema no tiene identidad de operario (el acceso es una cookie compartida), así que es débil como identidad y alcanza para lo que se pidió: que si alguien la usa siempre, se vea.';
end $$;
