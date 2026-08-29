-- ROLLBACK DEL CORTE — FRUTAMAX.
-- Deshace la puesta a cero + carga y deja la base exactamente como estaba.
-- Es para "corrí el script y salió mal", NO para deshacer una semana de
-- operación: si ya pasó algo del lado nuevo, se corta y no toca nada.
-- La migración del tipo NO se revierte acá (ver el pie del archivo).

begin;

-- ---------------------------------------------------------------------------
-- GUARDA — ¿PASÓ ALGO DESPUÉS DEL CORTE?
-- ---------------------------------------------------------------------------
do $$
declare hubo text;
begin
    select string_agg(que, ', ') into hubo from (
        select 'reprocesos normales del ' || fecha_operacion as que
        from reprocesos
        where tipo = 'normal' and anulado_el is null and fecha_operacion >= date '2026-08-31'
        union all
        select 'movimientos de stock del ' || fecha_operacion
        from movimientos_stock
        where anulado_el is null and fecha_operacion >= date '2026-08-31'
          and tipo not in ('cierre_modelo_viejo', 'stock_inicial')
        union all
        select 'compras recepcionadas el ' || (procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
        from compras
        where estado = 'recepcionado'
          and (procesada_el at time zone 'America/Argentina/Buenos_Aires')::date >= date '2026-08-31'
        union all
        select 'renglones armados el ' || (armado_el at time zone 'America/Argentina/Buenos_Aires')::date
        from pedidos_renglones
        where armado_el is not null and anulado_el is null
          and (armado_el at time zone 'America/Argentina/Buenos_Aires')::date >= date '2026-08-31'
    ) t;
    if hubo is not null then
        raise exception 'YA HAY OPERACIÓN DESPUÉS DEL CORTE (%). El rollback no corre: habría que decidir a mano qué pasa con eso.', hubo;
    end if;
end $$;

-- ---------------------------------------------------------------------------
-- PASO 1 — LAS CAJAS ARMADAS
-- ---------------------------------------------------------------------------
delete from reprocesos_consumos
where reproceso_id in (select id from reprocesos where tipo = 'inicial');

delete from reprocesos where tipo = 'inicial';

-- ---------------------------------------------------------------------------
-- PASO 2 — EL STOCK INICIAL Y LOS COMPENSATORIOS
-- ---------------------------------------------------------------------------
delete from movimientos_stock
where tipo in ('stock_inicial', 'cierre_modelo_viejo');

-- ---------------------------------------------------------------------------
-- PASO 3 — LAS FICHAS DE LAS GUÍAS R, DE VUELTA COMO ESTABAN
-- ---------------------------------------------------------------------------
update reprocesos r
set ficha_id = b.ficha_id
from corte_respaldo_fichas_reprocesos b
where b.reproceso_id = r.id;

delete from corte_respaldo_fichas_reprocesos;

-- ---------------------------------------------------------------------------
-- CONTROL — TIENE QUE QUEDAR TODO EN CERO
-- ---------------------------------------------------------------------------
do $$
begin
    if exists (select 1 from movimientos_stock where tipo in ('stock_inicial', 'cierre_modelo_viejo'))
       or exists (select 1 from reprocesos where tipo = 'inicial')
       or exists (select 1 from corte_respaldo_fichas_reprocesos) then
        raise exception 'El rollback no dejó la base limpia';
    end if;
end $$;

commit;

-- La migración del tipo (db/agregar_cierre_modelo_viejo.sql) NO se revierte:
-- agregar un valor al check y una tabla vacía no rompe nada, y volver atrás
-- obligaría a borrar el respaldo. Si hiciera falta igual, es:
--     drop table corte_respaldo_fichas_reprocesos;
--     alter table movimientos_stock drop constraint movimientos_stock_tipo_check;
--     alter table movimientos_stock add constraint movimientos_stock_tipo_check
--         check (tipo in ('ajuste', 'merma', 'reingreso_rechazo', 'stock_inicial'));
-- y eso SOLO corre si no quedó ningún movimiento de cierre vivo.
