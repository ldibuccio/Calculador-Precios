-- VERIFICADOR de la Entrega 3 (los lotes elegidos del armado de pedido).
--
-- ############################################################################
-- SE PEGA EN TRES VECES, UNA POR BLOQUE. NUNCA DE CORRIDO.
--
-- La primera versión de este verificador era UN bloque `do` de 5983
-- caracteres, y el editor de Supabase LO TRUNCÓ a la mitad —en el medio de un
-- caso— y le concatenó código propio abajo (un `ALTER TABLE ... ENABLE ROW
-- LEVEL SECURITY` con un comentario "Added by Supabase"). El error que
-- devolvió fue `unterminated dollar-quoted string`, que no dice una palabra
-- de lo que pasó de verdad.
--
-- Por eso ahora son tres bloques cortos (ninguno pasa los 2500 caracteres) y
-- cada uno se deshace solo con su propio `raise`. Si alguno se trunca, muere
-- sin haber escrito nada — un bloque `do` es UNA sentencia: o parsea entero o
-- no se ejecuta nada.
--
--   BLOQUE A: lo que más importa. Que el MISMO lote entre en DOS renglones
--             distintos (detecta un unique mal puesto) y que el cascade
--             funcione. SIEMPRE termina en error: eso es lo que deshace la
--             prueba.
--   BLOQUE B: que las reglas RECHACEN de verdad. También termina en error.
--   BLOQUE C: la consulta final. Se espera OK en las 9. No escribe nada.
--
-- Los bloques A y B insertan un pedido y renglones DE PRUEBA en las tablas
-- reales. Se puede: el esquema no tiene un solo trigger (verificado sobre
-- db/esquema_completo.sql), así que un insert directo no dispara nada, y el
-- `raise` revierte la transacción entera. El chequeo 08 del bloque C
-- confirma que no quedó nada.
-- ############################################################################


-- ############################################################################
-- BLOQUE A — el mismo lote en dos renglones, y el cascade
-- ############################################################################

do $$
declare p bigint; ra bigint; rb bigint; n int; mal text := '';
begin
    insert into pedidos (cliente_id, fecha_operacion, origen, texto_original)
    values ((select min(id) from clientes), date '1900-01-01', 'texto', 'PRUEBA DEL VERIFICADOR')
    returning id into p;
    insert into pedidos_renglones (pedido_id, cantidad) values (p, 10) returning id into ra;
    insert into pedidos_renglones (pedido_id, cantidad) values (p, 10) returning id into rb;

    -- Dos renglones del mismo pedido saliendo del MISMO lote es lo normal.
    -- El lote 999999 no existe a propósito: es polimórfico y sin FK.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (ra, 'guia', 999999, 6), (rb, 'guia', 999999, 3);
    exception when others then
        mal := mal || ' | A1 no entraron los dos: ' || sqlerrm;
    end;
    select count(*) into n from pedidos_renglones_lotes_elegidos where renglon_id in (ra, rb);
    if n <> 2 then mal := mal || ' | A1 quedaron ' || n || ' de 2'; end if;

    -- Borrar el renglón se lleva su corrección.
    delete from pedidos_renglones where id = rb;
    select count(*) into n from pedidos_renglones_lotes_elegidos where renglon_id = rb;
    if n <> 0 then mal := mal || ' | A2 quedaron ' || n || ' colgadas (falta el cascade)'; end if;

    if mal = '' then
        raise exception 'BLOQUE A OK — el mismo lote entra en dos renglones y el cascade limpia. Este error es DELIBERADO: deshace la prueba.';
    else
        raise exception 'BLOQUE A CON PROBLEMAS:%', mal;
    end if;
end $$;


-- ############################################################################
-- BLOQUE B — que las reglas rechacen de verdad
-- ############################################################################

do $$
declare p bigint; r bigint; mal text := '';
begin
    insert into pedidos (cliente_id, fecha_operacion, origen, texto_original)
    values ((select min(id) from clientes), date '1900-01-01', 'texto', 'PRUEBA DEL VERIFICADOR')
    returning id into p;
    insert into pedidos_renglones (pedido_id, cantidad) values (p, 10) returning id into r;
    insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
    values (r, 'guia', 999999, 6);

    -- 'compra' es el vocabulario de reprocesos_consumos: la confusión más probable.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (r, 'compra', 1, 1);
        mal := mal || ' | B1 entró lote_tipo compra';
    exception when check_violation then null;
              when others then mal := mal || ' | B1 rechazó por otra cosa: ' || sqlerrm;
    end;

    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (r, 'ajuste', 1, 0);
        mal := mal || ' | B2 entró una corrección de 0 bultos';
    exception when check_violation then null;
              when others then mal := mal || ' | B2 rechazó por otra cosa: ' || sqlerrm;
    end;

    -- El mismo lote DOS VECES en el MISMO renglón: dos verdades sobre lo mismo.
    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (r, 'guia', 999999, 4);
        mal := mal || ' | B3 entró el mismo lote dos veces en un renglón';
    exception when unique_violation then null;
              when others then mal := mal || ' | B3 rechazó por otra cosa: ' || sqlerrm;
    end;

    begin
        insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos)
        values (-1, 'guia', 1, 1);
        mal := mal || ' | B4 entró una corrección de un renglón inexistente';
    exception when foreign_key_violation then null;
              when others then mal := mal || ' | B4 rechazó por otra cosa: ' || sqlerrm;
    end;

    if mal = '' then
        raise exception 'BLOQUE B OK — los cuatro rechazos funcionaron. Este error es DELIBERADO: deshace la prueba.';
    else
        raise exception 'BLOQUE B CON PROBLEMAS:%', mal;
    end if;
end $$;


-- ############################################################################
-- BLOQUE C — leer lo que quedó armado. Se esperan 9 OK.
-- ############################################################################

with t as (select 'pedidos_renglones_lotes_elegidos'::regclass as tabla)
select n, verificacion, resultado from (
    select 1 as n, '01 - la tabla existe' as verificacion,
           case when to_regclass('public.pedidos_renglones_lotes_elegidos') is not null
                then 'OK' else 'FALLA' end as resultado
    union all
    select 2, '02 - renglon_id: FK con on delete cascade',
           case when count(*) = 1 then 'OK' else 'FALLA: falta la FK o no es cascade' end
    from pg_constraint, t
    where conrelid = t.tabla and contype = 'f'
      and confrelid = 'pedidos_renglones'::regclass and confdeltype = 'c'
    union all
    select 3, '03 - lote_origen_id SIN FK (polimorfico)',
           case when count(*) = 1 then 'OK — la unica FK es la del renglon'
                else 'FALLA: hay ' || count(*) || ' FK' end
    from pg_constraint, t where conrelid = t.tabla and contype = 'f'
    union all
    select 4, '04 - lote_tipo: el check nombra los CINCO tipos',
           case when count(*) = 1 then 'OK' else 'FALLA: falta el check o algun tipo' end
    from pg_constraint, t
    where conrelid = t.tabla and contype = 'c'
      and pg_get_constraintdef(oid) ~ 'lote_tipo.*guia.*reproceso.*reingreso_rechazo.*ajuste.*stock_inicial'
    union all
    select 5, '05 - bultos: el check exige mayor a cero',
           case when count(*) = 1 then 'OK' else 'FALLA: el check no esta' end
    from pg_constraint, t
    where conrelid = t.tabla and contype = 'c' and pg_get_constraintdef(oid) like '%bultos%'
    union all
    select 6, '06 - unique (renglon_id, lote_tipo, lote_origen_id)',
           case when count(*) = 1 then 'OK' else 'FALLA: no esta o es sobre otras columnas' end
    from pg_indexes
    where tablename = 'pedidos_renglones_lotes_elegidos' and indexdef like '%UNIQUE%'
      and indexdef like '%renglon_id%' and indexdef like '%lote_tipo%'
      and indexdef like '%lote_origen_id%'
    union all
    select 7, '07 - lote_origen_id y bultos son NOT NULL',
           case when count(*) = 2 then 'OK' else 'FALLA: alguna acepta NULL' end
    from information_schema.columns
    where table_name = 'pedidos_renglones_lotes_elegidos'
      and column_name in ('lote_origen_id', 'bultos') and is_nullable = 'NO'
    union all
    select 8, '08 - la tabla esta vacia: A y B no dejaron nada',
           case when (select count(*) from pedidos_renglones_lotes_elegidos) = 0 then 'OK — vacia'
                else 'MIRAR: hay ' || (select count(*) from pedidos_renglones_lotes_elegidos) end
    union all
    select 9, '09 - no quedo ningun pedido de prueba',
           case when (select count(*) from pedidos where texto_original like '%PRUEBA DEL VERIFICADOR%') = 0
                then 'OK' else 'MIRAR: quedaron pedidos de prueba' end
) resultado
order by n;
