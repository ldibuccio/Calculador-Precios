-- VERIFICADOR de db/normalizar_nombre_operario.sql.
--
-- SE PEGA EN DOS VECES, NO DE CORRIDO. El editor de Supabase muestra solo el
-- resultado de la última sentencia.
--   PASO 1: el bloque `do`. SIEMPRE termina en error, a propósito: así deshace
--           lo que insertó para probar. Lo que hay que leer es el mensaje.
--   PASO 2: la consulta final. Se espera OK en las 5.

-- ===================== PASO 1 — PROBAR QUE EL ÍNDICE PLIEGA =====================
--
-- Prueba la REGLA, no su definición. Leer que el índice dice "translate" no
-- dice nada sobre si rechaza: eso ya nos pasó con un check que existía y no
-- hacía lo que decía.

do $$
declare
    base_id bigint;
    malos text := '';
    bien  text := '';
begin
    insert into operarios_deposito (nombre) values ('Rubén Verificador')
    returning id into base_id;

    -- 1. La misma persona SIN LA TILDE. Es el caso que se coló en producción.
    begin
        insert into operarios_deposito (nombre) values ('Ruben Verificador');
        malos := malos || E'\n  ENTRÓ el mismo nombre SIN LA TILDE ("Ruben" al lado de "Rubén")';
    exception when unique_violation then
        bien := bien || E'\n  pliega las tildes';
    end;

    -- 2. Mayúsculas y espacios de más: la regla vieja, que tiene que seguir.
    begin
        insert into operarios_deposito (nombre) values ('  RUBÉN   VERIFICADOR ');
        malos := malos || E'\n  ENTRÓ el mismo nombre con otras MAYÚSCULAS Y ESPACIOS';
    exception when unique_violation then
        bien := bien || E'\n  sigue plegando mayúsculas y espacios de más';
    end;

    -- 3. Las dos cosas juntas, que es como se escribe de verdad cuando hay apuro.
    begin
        insert into operarios_deposito (nombre) values ('ruben  verificador');
        malos := malos || E'\n  ENTRÓ el mismo nombre sin tilde Y con otras mayúsculas';
    exception when unique_violation then
        bien := bien || E'\n  pliega tildes y mayúsculas a la vez';
    end;

    -- 4. La ñ, que la migración pliega a propósito.
    begin
        insert into operarios_deposito (nombre) values ('Muñoz Verificador');
        begin
            insert into operarios_deposito (nombre) values ('Munoz Verificador');
            malos := malos || E'\n  ENTRÓ "Munoz" al lado de "Muñoz" (la ñ no se está plegando)';
        exception when unique_violation then
            bien := bien || E'\n  pliega la ñ';
        end;
    exception when others then
        malos := malos || E'\n  no se pudo probar la ñ: ' || sqlerrm;
    end;

    -- 5. Y DOS PERSONAS DISTINTAS tienen que poder entrar las dos. Un índice
    --    que pliega de más es tan malo como uno que pliega de menos: dejaría
    --    afuera a alguien del depósito sin explicación.
    begin
        insert into operarios_deposito (nombre) values ('Marcelo Verificador');
        bien := bien || E'\n  deja entrar a dos personas distintas';
    exception when others then
        malos := malos || E'\n  NO ENTRÓ un nombre distinto (el índice pliega de más): ' || sqlerrm;
    end;

    if malos <> '' then
        raise exception E'PASO 1 — HAY PROBLEMAS:%\n\n(y esto SÍ es un problema; nada quedó escrito)', malos;
    end if;
    raise exception E'PASO 1 OK — el índice pliega lo que tiene que plegar:%\n\nEste error es DELIBERADO: deshace lo que la prueba insertó. Seguí con el paso 2.', bien;
end $$;

-- ===================== PASO 2 — LEER LO QUE QUEDÓ ARMADO =======================
select n, verificacion, resultado from (
    select 1 as n, '01 - el índice único existe y es ÚNICO' as verificacion,
           case when count(*) = 1 then 'OK' else 'FALLA: no está o no es único' end as resultado
    from pg_indexes
    where tablename = 'operarios_deposito' and indexname = 'operarios_deposito_nombre_unico'
      and indexdef like 'CREATE UNIQUE INDEX%'

    union all
    select 2, '02 - pliega tildes Y espacios internos, sin depender de unaccent',
           case when count(*) = 1 then 'OK' else 'FALLA: sigue con la regla vieja o usa unaccent' end
    from pg_indexes
    where tablename = 'operarios_deposito' and indexname = 'operarios_deposito_nombre_unico'
      and indexdef like '%translate%' and indexdef like '%lower%' and indexdef like '%btrim%'
      and indexdef like '%regexp_replace%' and indexdef not like '%unaccent%'

    union all
    select 3, '03 - no quedó ningún índice con la regla vieja dando vueltas',
           case when count(*) = 0 then 'OK' else 'FALLA: hay ' || count(*) || ' índice(s) sin translate' end
    from pg_indexes
    where tablename = 'operarios_deposito' and indexdef like '%UNIQUE%'
      and indexdef like '%btrim%' and (indexdef not like '%translate%' or indexdef not like '%regexp_replace%')

    union all
    select 4, '04 - no hay operarios que solo se distingan por tildes',
           case when count(*) = 0 then 'OK — ' || (select count(*) from operarios_deposito) || ' operarios cargados'
                else 'FALLA: ' || count(*) || ' nombre(s) repetido(s)' end
    from (
        select 1 from operarios_deposito
        group by lower(translate(regexp_replace(btrim(nombre), '\s+', ' ', 'g'), 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'))
        having count(*) > 1
    ) d

    union all
    select 5, '05 - el comentario dice que también se pliegan las tildes',
           case when col_description('operarios_deposito'::regclass,
                                     (select ordinal_position from information_schema.columns
                                      where table_name = 'operarios_deposito' and column_name = 'activo')) like '%TILDES%'
                then 'OK' else 'FALLA: el comentario quedó con la regla vieja' end
) todo order by n;
