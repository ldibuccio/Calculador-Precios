-- VERIFICADOR de la etapa 2 (freno + desglose del reproceso).
--
-- SE PEGA EN DOS VECES, NO DE CORRIDO. El editor de Supabase muestra solo el
-- resultado de la ÚLTIMA sentencia: si se pegan juntos y el bloque `do` falla,
-- la tabla de abajo se muestra igual y el error queda tapado — que es
-- exactamente el modo de fallar que este verificador viene a evitar.
--
--   PASO 1: el bloque `do`. Tiene que terminar SIN DECIR NADA. Si dice algo,
--           el check no hace lo que dice y no hay nada más que mirar.
--   PASO 2: la consulta final. Se espera OK en las 9.
--
-- DOS PARTES, y la primera es la que importa:
--
--   El bloque `do` PRUEBA QUE EL CHECK RECHAZA. Leer que un constraint existe
--   no dice nada sobre si funciona — en Postgres un check que evalúa a NULL se
--   da por cumplido, y así se nos coló uno que dejaba pasar una excepción sin
--   operario. Acá se intentan los tres casos malos de verdad; si alguno ENTRA,
--   el bloque corta con el detalle y la consulta final no llega a correrse,
--   que es el resultado correcto: un check roto es un freno, no un renglón
--   más de una tabla.
--
--   NO DEJA NADA: lo que se inserta para probar se borra en el mismo bloque, y
--   el bloque es UNA sentencia, así que si algo revienta se deshace entero.
--   La consulta final vuelve a comprobar que no quedó ninguna fila de prueba.
--
--   La consulta final LEE el resto (columnas, índices, comentarios) y devuelve
--   filas: el editor de Supabase muestra solo el resultado de la última.
--
-- Se espera que el PASO 1 no diga nada y el PASO 2 dé OK en las 9.

-- ===================== PASO 1 — PROBAR QUE EL CHECK RECHAZA =====================

do $$
declare
    art bigint;
    op  bigint;
    id_guia bigint;
    ok boolean;
    malos text := '';
begin
    select id into art from articulos limit 1;
    if art is null then
        raise exception 'La base no tiene artículos: el verificador no puede probar el check.';
    end if;

    insert into operarios_deposito (nombre) values ('__prueba del verificador__')
    returning id into op;

    -- 1. Motivo SIN operario tiene que rebotar.
    ok := false;
    begin
        insert into reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                                bultos_segunda, bultos_merma, excepcion_motivo)
        values (art, current_date, 10, 8, 1, 1, '__prueba__')
        returning id into id_guia;
        delete from reprocesos where id = id_guia;
    exception when check_violation then ok := true; end;
    if not ok then malos := malos || 'entró una excepción CON MOTIVO Y SIN OPERARIO; '; end if;

    -- 2. Operario SIN motivo tiene que rebotar.
    ok := false;
    begin
        insert into reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                                bultos_segunda, bultos_merma, excepcion_operario_id)
        values (art, current_date, 10, 8, 1, 1, op)
        returning id into id_guia;
        delete from reprocesos where id = id_guia;
    exception when check_violation then ok := true; end;
    if not ok then malos := malos || 'entró una excepción CON OPERARIO Y SIN MOTIVO; '; end if;

    -- 3. Motivo en blanco tiene que rebotar: no es una excepción, es un pase libre.
    ok := false;
    begin
        insert into reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                                bultos_segunda, bultos_merma, excepcion_motivo, excepcion_operario_id)
        values (art, current_date, 10, 8, 1, 1, '   ', op)
        returning id into id_guia;
        delete from reprocesos where id = id_guia;
    exception when check_violation then ok := true; end;
    if not ok then malos := malos || 'entró una excepción CON EL MOTIVO EN BLANCO; '; end if;

    -- 4. Y la completa tiene que ENTRAR, o el check estaría trabando de más.
    ok := true;
    begin
        insert into reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                                bultos_segunda, bultos_merma, excepcion_motivo, excepcion_operario_id)
        values (art, current_date, 10, 8, 1, 1, '__prueba__', op)
        returning id into id_guia;
        delete from reprocesos where id = id_guia;
    exception when others then ok := false; end;
    if not ok then malos := malos || 'NO entró una excepción completa (el check traba de más); '; end if;

    -- 5. Y el nombre normalizado tiene que ser único.
    ok := false;
    begin
        insert into operarios_deposito (nombre) values ('  __PRUEBA DEL VERIFICADOR__ ');
    exception when unique_violation then ok := true; end;
    if not ok then malos := malos || 'entraron dos operarios con el mismo nombre normalizado; '; end if;

    delete from operarios_deposito where nombre ilike '%prueba del verificador%';

    if malos <> '' then
        raise exception 'EL CHECK NO HACE LO QUE DICE: %', malos;
    end if;
end $$;

-- ===================== PASO 2 — LEER LO QUE QUEDÓ ARMADO =======================
select n, verificacion, resultado from (
    select 1 as n, '01 - operarios_deposito existe y arranca vacía' as verificacion,
           case when not exists (select 1 from pg_class where relname = 'operarios_deposito')
                then 'FALLA: la tabla no está'
                when (select count(*) from operarios_deposito) = 0 then 'OK — vacía, se carga desde Administración'
                else 'OK — ya tiene ' || (select count(*) from operarios_deposito) || ' operarios' end as resultado

    union all
    select 2, '02 - el nombre del operario es único NORMALIZADO (no entra "juan" y "Juan")',
           case when count(*) = 1 then 'OK' else 'FALLA: falta el índice único sobre lower(btrim(nombre))' end
    from pg_indexes
    where tablename = 'operarios_deposito' and indexname = 'operarios_deposito_nombre_unico'
      and indexdef like '%lower(btrim(nombre))%'

    union all
    select 3, '03 - consumos_editados: boolean, NOT NULL, default false',
           case when count(*) = 1 then 'OK' else 'FALLA: no está o no es como se esperaba' end
    from information_schema.columns
    where table_name = 'reprocesos' and column_name = 'consumos_editados'
      and data_type = 'boolean' and is_nullable = 'NO' and column_default = 'false'

    union all
    select 4, '04 - excepcion_motivo: text y NULLABLE (NULL = no hubo excepción)',
           case when count(*) = 1 then 'OK' else 'FALLA' end
    from information_schema.columns
    where table_name = 'reprocesos' and column_name = 'excepcion_motivo'
      and data_type = 'text' and is_nullable = 'YES'

    union all
    select 5, '05 - excepcion_operario_id apunta a operarios_deposito',
           case when count(*) = 1 then 'OK' else 'FALLA: no está la FK' end
    from pg_constraint c
    where c.conrelid = 'reprocesos'::regclass and c.contype = 'f'
      and c.confrelid = 'operarios_deposito'::regclass

    union all
    -- El bloque de arriba ya PROBÓ que rechaza; esto solo confirma que el que
    -- rechaza es el constraint que creemos, con el nombre que las migraciones
    -- futuras van a nombrar para reemplazarlo.
    select 6, '06 - el check que rechaza es reprocesos_excepcion_completa',
           case when count(*) = 1 then 'OK — y el bloque de arriba probó que rechaza'
                else 'FALLA: el check no está' end
    from pg_constraint
    where conrelid = 'reprocesos'::regclass and conname = 'reprocesos_excepcion_completa'

    union all
    select 7, '07 - el índice parcial para contar por operario y por día',
           case when count(*) = 1 then 'OK' else 'FALLA: el índice no está' end
    from pg_indexes
    where tablename = 'reprocesos' and indexname = 'reprocesos_excepcion_idx'
      and indexdef like '%WHERE (excepcion_motivo IS NOT NULL)%'

    union all
    select 8, '08 - las guías que ya existían quedaron sin excepción y sin editar, y la prueba no dejó nada',
           case when count(*) = 0
                     and not exists (select 1 from operarios_deposito where nombre ilike '%prueba del verificador%')
                then 'OK — ' || (select count(*) from reprocesos) || ' guías intactas'
                else 'FALLA: ' || count(*) || ' guías tocadas, o quedó una fila de prueba' end
    from reprocesos
    where consumos_editados or excepcion_motivo is not null or excepcion_operario_id is not null

    union all
    select 9, '09 - las tres columnas y la tabla tienen su comentario',
           case when count(*) = 3 and obj_description('operarios_deposito'::regclass) is not null
                then 'OK' else 'FALLA: falta alguno' end
    from information_schema.columns c
    where c.table_name = 'reprocesos'
      and c.column_name in ('consumos_editados', 'excepcion_motivo', 'excepcion_operario_id')
      and col_description('reprocesos'::regclass, c.ordinal_position) is not null
) todo order by n;
