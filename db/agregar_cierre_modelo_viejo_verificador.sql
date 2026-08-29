-- VERIFICADOR DE LA MIGRACIÓN DEL TIPO 'cierre_modelo_viejo'.
-- No deja nada: todo pasa adentro de una transacción que termina en rollback.
-- Se espera OK en las 8.

begin;

create temp table resultado (n int, verificacion text, salio text);

do $$
declare art bigint; ok boolean;
begin
    select min(id) into art from articulos;
    if art is null then
        raise exception 'La base no tiene artículos: el verificador no puede correr';
    end if;

    -- 1. El tipo nuevo entra.
    begin
        insert into movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema)
        values (art, 'cierre_modelo_viejo', -10, 'prueba', current_date, 10);
        insert into resultado values (1, 'El tipo cierre_modelo_viejo se acepta', 'OK');
    exception when others then
        insert into resultado values (1, 'El tipo cierre_modelo_viejo se acepta', 'FALLA: ' || sqlerrm);
    end;

    -- 2. Signo libre: el compensatorio de un artículo en negativo es POSITIVO.
    begin
        insert into movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema)
        values (art, 'cierre_modelo_viejo', 180, 'prueba', current_date, -180);
        insert into resultado values (2, 'El cierre acepta cantidad positiva (los 9 en negativo)', 'OK');
    exception when others then
        insert into resultado values (2, 'El cierre acepta cantidad positiva (los 9 en negativo)', 'FALLA: ' || sqlerrm);
    end;

    -- 3. Los cuatro tipos de siempre siguen entrando.
    begin
        insert into movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema)
        values (art, 'ajuste', 1, 'prueba', current_date, 0),
               (art, 'merma', -1, 'prueba', current_date, 0),
               (art, 'reingreso_rechazo', 1, 'prueba', current_date, 0),
               (art, 'stock_inicial', 1, 'prueba', current_date, 0);
        insert into resultado values (3, 'Los cuatro tipos de siempre siguen entrando', 'OK');
    exception when others then
        insert into resultado values (3, 'Los cuatro tipos de siempre siguen entrando', 'FALLA: ' || sqlerrm);
    end;

    -- 4. Un tipo inventado se sigue rechazando.
    ok := false;
    begin
        insert into movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema)
        values (art, 'cualquier_cosa', 1, 'prueba', current_date, 0);
    exception when check_violation then ok := true;
    end;
    insert into resultado values (4, 'Un tipo inventado se rechaza',
        case when ok then 'OK' else 'FALLA: entró un tipo que no existe' end);

    -- 5. El cierre NO lleva costo (sigue siendo exclusivo del reingreso y del stock inicial).
    ok := false;
    begin
        insert into movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema, costo_por_bulto)
        values (art, 'cierre_modelo_viejo', -10, 'prueba', current_date, 10, 100);
    exception when check_violation then ok := true;
    end;
    insert into resultado values (5, 'El cierre con costo_por_bulto se rechaza',
        case when ok then 'OK' else 'FALLA: le entró un costo' end);

    -- 6. El cierre no puede ser el lote al que se dirige una merma.
    ok := false;
    begin
        insert into movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema, lote_tipo, lote_origen_id)
        values (art, 'merma', -1, 'prueba', current_date, 0, 'cierre_modelo_viejo', 1);
    exception when check_violation then ok := true;
    end;
    insert into resultado values (6, 'Una merma no se puede dirigir a un lote de cierre',
        case when ok then 'OK' else 'FALLA: aceptó dirigirse a un cierre' end);
end $$;

-- 7. La tabla de respaldo existe y está vacía.
insert into resultado
select 7, 'La tabla de respaldo de fichas existe y está vacía',
       case when count(*) = 0 then 'OK' else 'FALLA: ya tiene ' || count(*) || ' filas' end
from corte_respaldo_fichas_reprocesos;

-- 8. No se perdió ningún otro check de la tabla.
insert into resultado
select 8, 'Los 15 checks de movimientos_stock siguen estando',
       case when count(*) = 15 then 'OK' else 'FALLA: hay ' || count(*) || ' y esperaba 15' end
from pg_constraint
where conrelid = 'movimientos_stock'::regclass and contype = 'c';

select n, verificacion, salio from resultado order by n;

rollback;
