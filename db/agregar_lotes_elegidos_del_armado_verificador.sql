-- VERIFICADOR de la Entrega 3 (los lotes elegidos del armado de pedido).
--
-- SE PEGA EN DOS VECES, NO DE CORRIDO. El editor de Supabase muestra solo el
-- resultado de la ÚLTIMA sentencia: si se pegan juntos y el bloque `do` falla,
-- la tabla de abajo se muestra igual y el error queda tapado — que es
-- exactamente el modo de fallar que este verificador viene a evitar.
--
--   PASO 1: el bloque `do`. SIEMPRE termina en error, a propósito: así deshace
--           lo que insertó para probar, sin depender de ningún `delete`. Lo que
--           hay que leer es el mensaje — dice "PASO 1 OK" o nombra los
--           problemas.
--   PASO 2: la consulta final. Se espera OK en las 9.
--
-- El bloque inserta un pedido y dos renglones DE PRUEBA en las tablas reales.
-- Se puede: el esquema no tiene un solo trigger (verificado sobre
-- db/esquema_completo.sql), así que un insert directo no dispara nada. Y el
-- `raise exception` del final revierte la transacción entera: el pedido, los
-- renglones y todo lo que se haya escrito se deshacen solos. El chequeo 08 del
-- paso 2 confirma que no quedó nada.


-- ############################################################################
-- PASO 1 — QUE LAS REGLAS RECHACEN DE VERDAD (pegar SOLO esto)
-- ############################################################################

do $$
declare
    cliente   bigint;
    pedido    bigint;
    renglon_a bigint;
    renglon_b bigint;
    problemas text := '';
    cuantas   int;
begin
    select id into cliente from clientes order by id limit 1;
    if cliente is null then
        raise exception 'No hay ningún cliente cargado, y este verificador necesita uno para armar el pedido de prueba.';
    end if;

    insert into pedidos (cliente_id, fecha_operacion, origen, texto_original)
    values (cliente, date '1900-01-01', 'texto', 'PRUEBA DEL VERIFICADOR - se deshace sola')
    returning id into pedido;

    insert into pedidos_renglones (pedido_id, cantidad) values (pedido, 10) returning id into renglon_a;
    insert into pedidos_renglones (pedido_id, cantidad) values (pedido, 10) returning id into renglon_b;

    -- CASO 1 — una corrección normal entra. lote_origen_id 999999 no existe en
    -- ninguna tabla A PROPÓSITO: el lote es polimórfico y sin FK, y si esto
    -- fallara sería porque alguien le puso una FK y rompió el diseño.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (renglon_a, 'guia', 999999, 6);
    exception when others then
        problemas := problemas || E'\n- CASO 1: una corrección normal NO entró (' || sqlerrm || ')';
    end;

    -- CASO 2 — un lote_tipo que no existe. Se prueba con 'compra' a propósito:
    -- es el vocabulario de reprocesos_consumos, la confusión más probable.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (renglon_a, 'compra', 1, 1);
        problemas := problemas || E'\n- CASO 2: entró un lote_tipo inválido (compra)';
    exception
        when check_violation then null;
        when others then
            problemas := problemas || E'\n- CASO 2: rechazó, pero no por el check (' || sqlerrm || ')';
    end;

    -- CASO 3 — cero bultos y bultos negativos. Una corrección que no mueve
    -- nada no es una corrección.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (renglon_a, 'ajuste', 1, 0);
        problemas := problemas || E'\n- CASO 3a: entró una corrección de 0 bultos';
    exception
        when check_violation then null;
        when others then
            problemas := problemas || E'\n- CASO 3a: rechazó, pero no por el check (' || sqlerrm || ')';
    end;

    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (renglon_a, 'ajuste', 1, -5);
        problemas := problemas || E'\n- CASO 3b: entró una corrección de bultos NEGATIVOS';
    exception
        when check_violation then null;
        when others then
            problemas := problemas || E'\n- CASO 3b: rechazó, pero no por el check (' || sqlerrm || ')';
    end;

    -- CASO 4 — el MISMO lote dos veces en el MISMO renglón: serían dos
    -- verdades sobre lo mismo y la suma dejaría de ser una suma.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (renglon_a, 'guia', 999999, 4);
        problemas := problemas || E'\n- CASO 4: entró el mismo lote DOS VECES en el mismo renglón';
    exception
        when unique_violation then null;
        when others then
            problemas := problemas || E'\n- CASO 4: rechazó, pero no por el unique (' || sqlerrm || ')';
    end;

    -- CASO 5 — EL MÁS IMPORTANTE. El mismo lote en DOS renglones distintos
    -- tiene que entrar: dos renglones del mismo pedido pueden salir del mismo
    -- lote, y eso es lo normal. Si el unique estuviera mal puesto (sobre el
    -- lote y no sobre la pareja), esto se rechazaría y el que arma no podría
    -- decir la verdad.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (renglon_b, 'guia', 999999, 3);
    exception when others then
        problemas := problemas || E'\n- CASO 5: el mismo lote en OTRO renglón no entró (' || sqlerrm || ')';
    end;

    select count(*) into cuantas from pedidos_renglones_lotes_elegidos
    where renglon_id in (renglon_a, renglon_b);
    if cuantas <> 2 then
        problemas := problemas || E'\n- CASO 5: quedaron ' || cuantas || ' correcciones y tenían que quedar 2';
    end if;

    -- CASO 6 — un renglón que no existe. La FK tiene que rechazarlo: una
    -- corrección colgada de la nada no se puede leer nunca más.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (-1, 'guia', 1, 1);
        problemas := problemas || E'\n- CASO 6: entró una corrección de un renglón inexistente';
    exception
        when foreign_key_violation then null;
        when others then
            problemas := problemas || E'\n- CASO 6: rechazó, pero no por la FK (' || sqlerrm || ')';
    end;

    -- CASO 7 — el on delete cascade. Es la red: un renglón que desaparezca no
    -- puede dejar su corrección colgada apuntándole.
    delete from pedidos_renglones where id = renglon_b;
    select count(*) into cuantas from pedidos_renglones_lotes_elegidos where renglon_id = renglon_b;
    if cuantas <> 0 then
        problemas := problemas || E'\n- CASO 7: borré el renglón y quedaron ' || cuantas || ' correcciones colgadas (falta el on delete cascade)';
    end if;

    -- El raise es SIEMPRE, con problemas o sin ellos: es lo que deshace el
    -- pedido, los dos renglones y las correcciones de prueba. Sin él habría
    -- que confiar en un `delete` que puede quedarse corto.
    if problemas = '' then
        raise exception 'PASO 1 OK — los 7 casos se comportaron como se esperaba. Este error es DELIBERADO: revierte todo lo que el verificador escribió, así no queda un pedido de prueba en producción.';
    else
        raise exception 'PASO 1 CON PROBLEMAS:%', problemas;
    end if;
end $$;


-- ############################################################################
-- PASO 2 — LEER LO QUE QUEDÓ ARMADO (pegar SOLO esto, después del paso 1)
-- ############################################################################

select n, verificacion, resultado from (
    select 1 as n, '01 - la tabla pedidos_renglones_lotes_elegidos existe' as verificacion,
           case when exists (select 1 from pg_class where relname = 'pedidos_renglones_lotes_elegidos')
                then 'OK' else 'FALLA: no está' end as resultado

    union all
    select 2, '02 - renglon_id: FK a pedidos_renglones CON on delete cascade',
           case when count(*) = 1 then 'OK — la corrección se va con su renglón'
                else 'FALLA: falta la FK o no es cascade' end
    from pg_constraint
    where conrelid = 'pedidos_renglones_lotes_elegidos'::regclass
      and contype = 'f' and confrelid = 'pedidos_renglones'::regclass
      and confdeltype = 'c'

    union all
    -- El lote es POLIMÓRFICO: apunta a compras, reprocesos o movimientos_stock
    -- según su tipo. Una FK acá lo rompería, así que la ausencia se verifica.
    select 3, '03 - lote_origen_id SIN FK (polimórfico a propósito)',
           case when count(*) = 1 then 'OK — la única FK de la tabla es la del renglón'
                else 'FALLA: hay ' || count(*) || ' FK y tendría que haber una sola' end
    from pg_constraint
    where conrelid = 'pedidos_renglones_lotes_elegidos'::regclass and contype = 'f'

    union all
    -- El bloque de arriba ya PROBÓ que rechaza 'compra'; esto confirma que los
    -- cinco tipos buenos están nombrados, y con el mismo vocabulario que
    -- movimientos_stock.lote_tipo y core/stock.py.
    select 4, '04 - lote_tipo: el check nombra los CINCO tipos de lote',
           case when count(*) = 1 then 'OK — y el paso 1 probó que rechaza uno inválido'
                else 'FALLA: el check no está o le falta algún tipo' end
    from pg_constraint
    where conrelid = 'pedidos_renglones_lotes_elegidos'::regclass and contype = 'c'
      and pg_get_constraintdef(oid) like '%lote_tipo%'
      and pg_get_constraintdef(oid) like '%guia%'
      and pg_get_constraintdef(oid) like '%reproceso%'
      and pg_get_constraintdef(oid) like '%reingreso_rechazo%'
      and pg_get_constraintdef(oid) like '%ajuste%'
      and pg_get_constraintdef(oid) like '%stock_inicial%'

    union all
    select 5, '05 - bultos: el check exige mayor a cero',
           case when count(*) = 1 then 'OK — y el paso 1 probó que rechaza 0 y negativos'
                else 'FALLA: el check no está' end
    from pg_constraint
    where conrelid = 'pedidos_renglones_lotes_elegidos'::regclass and contype = 'c'
      and pg_get_constraintdef(oid) like '%bultos%'

    union all
    select 6, '06 - unique sobre (renglon_id, lote_tipo, lote_origen_id)',
           case when count(*) = 1 then 'OK — el mismo lote no se repite en un renglón, pero SÍ puede estar en dos renglones'
                else 'FALLA: no está el unique, o es sobre otras columnas' end
    from pg_indexes
    where tablename = 'pedidos_renglones_lotes_elegidos'
      and indexdef like '%UNIQUE%'
      and indexdef like '%renglon_id%'
      and indexdef like '%lote_tipo%'
      and indexdef like '%lote_origen_id%'

    union all
    select 7, '07 - lote_origen_id y bultos son NOT NULL',
           case when count(*) = 2 then 'OK' else 'FALLA: alguna acepta NULL' end
    from information_schema.columns
    where table_name = 'pedidos_renglones_lotes_elegidos'
      and column_name in ('lote_origen_id', 'bultos')
      and is_nullable = 'NO'

    union all
    -- Lo que el paso 1 escribió tiene que haberse ido con su raise. Si acá hay
    -- filas, o quedó basura de la prueba o alguien ya está corrigiendo lotes.
    select 8, '08 - la tabla arranca vacía y la prueba no dejó nada',
           case when (select count(*) from pedidos_renglones_lotes_elegidos) = 0
                then 'OK — vacía'
                else 'MIRAR: hay ' || (select count(*) from pedidos_renglones_lotes_elegidos)
                     || ' correcciones. Si el código todavía no salió, es basura del paso 1.' end

    union all
    select 9, '09 - los comentarios están cargados (la tabla y sus 3 columnas)',
           case when count(*) = 4 then 'OK'
                else 'FALLA: hay ' || count(*) || ' comentarios de 4' end
    from (
        select obj_description('pedidos_renglones_lotes_elegidos'::regclass) as texto
        union all
        select col_description('pedidos_renglones_lotes_elegidos'::regclass, ordinal_position::int)
        from information_schema.columns
        where table_name = 'pedidos_renglones_lotes_elegidos'
          and column_name in ('lote_tipo', 'lote_origen_id', 'bultos')
    ) comentarios
    where texto is not null and btrim(texto) <> ''
) resultado
order by n;
