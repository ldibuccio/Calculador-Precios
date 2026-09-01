-- ############################################################################
-- ATENCIÓN — NO REUSAR ESTE SCRIPT COMO ESTÁ. NUNCA SE CORRIÓ.
--
-- Este verificador NO se ejecutó en el corte del 29/08/2026: usa vistas y
-- tablas temporales y habría fallado igual que el script de carga. El corte
-- se respaldó con dos consultas de UNA sola sentencia armadas a mano. Sus
-- verificaciones 04, 05, 11 y 12 (sueltos negativos, cajas por ficha, y las
-- dos del FIFO) SIGUEN SIN CORRERSE en Frutamax.
--
-- Se corrió en Frutamax el 29/08/2026 y TERMINÓ CON ERROR ESCRIBIENDO IGUAL
-- ('relation "foto" does not exist'). El editor SQL de Supabase NO sostiene el
-- `begin`: confirma cada sentencia por su cuenta, y las tablas/vistas
-- TEMPORALES no sobreviven de una sentencia a la siguiente. Terminó bien por
-- casualidad: el error cayó después del último paso. Si caía en el medio,
-- quedaba media base aplicada y media no.
--
-- ANTES DE REUSARLO (por ejemplo para Palmala): reescribirlo SIN temporales y
-- con todo lo que tenga que ser todo-o-nada adentro de un único
-- `do $$ ... end $$`. Ver CLAUDE.md, "SQL para el editor de Supabase", y el
-- incidente completo en db/APLICADO.md.
-- ############################################################################

-- VERIFICADOR DEL CORTE — FRUTAMAX.
-- No cuenta filas insertadas: corre LAS SEIS PATAS del Stock del Sistema y
-- las compara contra la foto aprobada. Solo lectura.
-- Se espera OK en las 12.

drop view if exists corte_stock_vivo;
create temp view corte_stock_vivo as
with entradas as (
    select articulo_id, sum(cantidad_cajones_real) as total
    from compras where estado = 'recepcionado' group by articulo_id
), vigentes as (
    select distinct on (cliente_id, fecha_operacion) id
    from pedidos where anulado_el is null
    order by cliente_id, fecha_operacion, creado_en desc
), salidas as (
    select r.articulo_id, sum(coalesce(r.cantidad_armada, r.cantidad)) as total
    from pedidos_renglones r join vigentes v on v.id = r.pedido_id
    where r.armado_el is not null and r.anulado_el is null and r.articulo_id is not null
    group by r.articulo_id
), reingresos as (
    select articulo_id, sum(cantidad) as total from movimientos_stock
    where anulado_el is null and tipo = 'reingreso_rechazo'
      and (destino_rechazo is null or destino_rechazo = 'stock')
    group by articulo_id
), ajustes as (
    select articulo_id, sum(cantidad) as total from movimientos_stock
    where anulado_el is null and tipo <> 'reingreso_rechazo' group by articulo_id
), reproc as (
    select articulo_id, sum(bultos_primera) as entradas, sum(bultos_tomados) as salidas
    from reprocesos where anulado_el is null group by articulo_id
)
select a.id as articulo_id, a.nombre,
       coalesce(e.total, 0) + coalesce(r.total, 0) + coalesce(aj.total, 0)
       + coalesce(rp.entradas, 0) - coalesce(rp.salidas, 0) - coalesce(s.total, 0) as stock
from articulos a
left join entradas e on e.articulo_id = a.id
left join salidas s on s.articulo_id = a.id
left join reingresos r on r.articulo_id = a.id
left join ajustes aj on aj.articulo_id = a.id
left join reproc rp on rp.articulo_id = a.id;

-- El stock partido por porción, igual que el Cotejo (_SQL_STOCK_PARTIDO).
drop view if exists corte_cajas_por_ficha;
create temp view corte_cajas_por_ficha as
with vigentes as (
    select distinct on (cliente_id, fecha_operacion) id
    from pedidos where anulado_el is null
    order by cliente_id, fecha_operacion, creado_en desc
), armadas as (
    select articulo_id, ficha_id, sum(bultos_primera) as total
    from reprocesos where anulado_el is null and ficha_id is not null
    group by articulo_id, ficha_id
), salidas_ficha as (
    select r.articulo_id, r.ficha_id, sum(coalesce(r.cantidad_armada, r.cantidad)) as total
    from pedidos_renglones r join vigentes v on v.id = r.pedido_id
    where r.armado_el is not null and r.anulado_el is null
      and r.articulo_id is not null and r.ficha_id is not null
    group by r.articulo_id, r.ficha_id
), fichas_con_algo as (
    select articulo_id, ficha_id from armadas
    union
    select articulo_id, ficha_id from salidas_ficha
)
select f.articulo_id, f.ficha_id,
       coalesce(a.total, 0) - coalesce(s.total, 0) as cajas
from fichas_con_algo f
left join armadas a on a.articulo_id = f.articulo_id and a.ficha_id = f.ficha_id
left join salidas_ficha s on s.articulo_id = f.articulo_id and s.ficha_id = f.ficha_id;

drop table if exists corte_foto;
create temp table corte_foto (articulo_id bigint primary key, nombre text,
                        bultos numeric, costo numeric);
insert into corte_foto values
 (29, 'Morron Rojo',    44, 33000),
 (15, 'Tomate Redondo', 89, 43846.15),
 (20, 'Morron Verde',   25, 20000),
 (19, 'Zapallito',      44, 35000),
 (17, 'Berenjena',      17, 25000),
 ( 4, 'Mzn Gob',        73, 28000),
 ( 6, 'Mzn Granny',     25, 60000),
 (28, 'Pomelo',         21, 10000),
 (24, 'Mandarina',      41, 11000),
 (16, 'Tomate Perita',  45, 48536.59),
 (18, 'Pepino',         33, 23857.14),
 ( 7, 'Mzn Red',        20, 55000),
 (25, 'Limon',          23, 10000),
 ( 9, 'Pera',            5, 27000),
 (22, 'Mango',           4, 53000),
 (27, 'Ombligo',         8, 10000),
 (23, 'Palta',          10, 60353.66),
 (21, 'Tomate Cherry',   4, 41584.91);

-- Lo que tiene que quedar en el piso, por artículo: los sueltos de la foto
-- más las cajas de los dos reprocesos iniciales.
drop table if exists corte_esperado;
create temp table corte_esperado as
select f.articulo_id, f.nombre, f.bultos as sueltos,
       f.bultos + coalesce(c.cajas, 0) as stock_total
from corte_foto f
left join (values (19, 25::numeric), (17, 12::numeric)) as c(articulo_id, cajas)
       on c.articulo_id = f.articulo_id;

-- El FIFO del stock, resuelto en SQL: los lotes ordenados como los ordena
-- _entradas_y_salidas_stock_varios, y el total de salidas comiéndolos del más
-- viejo al más nuevo. Sirve para probar que el modelo nuevo arranca limpio.
-- (Las mermas dirigidas a un lote no cambian el resultado acá: todas apuntan
-- a lotes pre-corte, que el compensatorio deja consumidos igual.)
drop view if exists corte_fifo;
create temp view corte_fifo as
with lotes as (
    select (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date as fecha_orden,
           c.procesada_el as momento_orden, 'guia' as tipo_lote, c.id as origen_id,
           c.cantidad_cajones_real as cantidad, c.importe as costo_bulto, c.articulo_id
    from compras c where c.estado = 'recepcionado'
    union all
    select m.fecha_operacion, m.creado_en, m.tipo, m.id, m.cantidad, m.costo_por_bulto, m.articulo_id
    from movimientos_stock m
    where m.anulado_el is null and m.cantidad > 0
      and (m.destino_rechazo is null or m.destino_rechazo = 'stock')
    union all
    select rp.fecha_operacion, rp.creado_en, 'reproceso', rp.id, rp.bultos_primera,
           rp.costo_por_bulto_primera, rp.articulo_id
    from reprocesos rp where rp.anulado_el is null and rp.bultos_primera > 0
), vigentes as (
    select distinct on (cliente_id, fecha_operacion) id
    from pedidos where anulado_el is null
    order by cliente_id, fecha_operacion, creado_en desc
), salidas as (
    select articulo_id, sum(total) as total from (
        select r.articulo_id, sum(coalesce(r.cantidad_armada, r.cantidad)) as total
        from pedidos_renglones r join vigentes v on v.id = r.pedido_id
        where r.armado_el is not null and r.anulado_el is null and r.articulo_id is not null
        group by r.articulo_id
        union all
        select articulo_id, -sum(cantidad) from movimientos_stock
        where anulado_el is null and cantidad < 0 group by articulo_id
        union all
        select articulo_id, sum(bultos_tomados) from reprocesos
        where anulado_el is null group by articulo_id
    ) t group by articulo_id
), acumulado as (
    select l.*,
           sum(l.cantidad) over (partition by l.articulo_id
                                 order by l.fecha_orden, l.momento_orden, l.origen_id
                                 rows between unbounded preceding and current row) as hasta_aca,
           coalesce(s.total, 0) as salidas_totales
    from lotes l left join salidas s on s.articulo_id = l.articulo_id
)
select articulo_id, tipo_lote, origen_id, cantidad, costo_bulto,
       greatest(0, least(cantidad, hasta_aca - salidas_totales)) as restante
from acumulado;

-- ---------------------------------------------------------------------------
-- LAS 12 VERIFICACIONES Y LA FOTO, EN UNA SOLA TABLA.
-- ---------------------------------------------------------------------------
with sueltos_reales as (
    select v.articulo_id, v.nombre, v.stock,
           v.stock - coalesce((select sum(c.cajas) from corte_cajas_por_ficha c
                               where c.articulo_id = v.articulo_id), 0) as sueltos
    from corte_stock_vivo v
)
select * from (
    select 1 as n, '01 - Los 18 artículos de la foto, con las seis patas' as verificacion,
           coalesce('FALLA: ' || string_agg(e.nombre || ' da ' || v.stock
                                            || ' y esperaba ' || e.stock_total, ', '),
                    'OK - los 18 dan exacto') as resultado
    from corte_esperado e join corte_stock_vivo v on v.articulo_id = e.articulo_id
    where v.stock is distinct from e.stock_total

    union all
    select 2, '02 - Ningún otro artículo con stock',
           coalesce('FALLA: ' || string_agg(v.nombre || ' = ' || v.stock, ', '),
                    'OK - todo lo demás en cero')
    from corte_stock_vivo v
    where v.stock <> 0 and v.articulo_id not in (select articulo_id from corte_foto)

    union all
    select 3, '03 - Los SUELTOS por artículo (stock menos cajas de sus fichas)',
           coalesce('FALLA: ' || string_agg(x.nombre || ' suelta ' || x.sueltos
                                            || ' y esperaba ' || e.sueltos, ', '),
                    'OK - los 18 sueltos dan la foto')
    from corte_esperado e join sueltos_reales x on x.articulo_id = e.articulo_id
    where x.sueltos is distinct from e.sueltos

    union all
    select 4, '04 - Ningún suelto negativo (el síntoma de las cajas fantasma)',
           coalesce('FALLA: ' || string_agg(x.nombre || ' = ' || x.sueltos, ', '),
                    'OK - ninguno negativo')
    from sueltos_reales x where x.sueltos < 0

    union all
    select 5, '05 - Las cajas por ficha: solo la 5 (25) y la 7 (12)',
           coalesce('FALLA: ' || string_agg('ficha ' || c.ficha_id || ' = ' || c.cajas, ', '),
                    'OK - ficha 5 = 25 cajas, ficha 7 = 12 cajas, ninguna otra')
    from corte_cajas_por_ficha c
    where c.cajas <> 0 and (c.ficha_id, c.cajas) not in ((5, 25::numeric), (7, 12::numeric))

    union all
    select 6, '06 - Las dos fichas del corte están, y en su artículo',
           case when count(*) = 2 then 'OK - 5 en Zapallito y 7 en Berenjena'
                else 'FALLA: encontré ' || count(*) || ' de 2' end
    from corte_cajas_por_ficha c
    where (c.ficha_id, c.articulo_id, c.cajas) in ((5, 19, 25::numeric), (7, 17, 12::numeric))

    union all
    select 7, '07 - Ninguna guía R pre-corte quedó con ficha',
           case when count(*) = 0 then 'OK - las pre-corte, todas en NULL'
                else 'FALLA: quedan ' || count(*) || ' guías R con ficha antes del corte' end
    from reprocesos
    where anulado_el is null and ficha_id is not null and fecha_operacion < date '2026-08-31'

    union all
    select 8, '08 - La plata de los sueltos',
           case when coalesce(sum(cantidad * costo_por_bulto), 0) = 17522615.76
                     and coalesce(sum(cantidad), 0) = 531
                then 'OK - $17.522.615,76 en 531 bultos'
                else 'FALLA: $' || coalesce(sum(cantidad * costo_por_bulto), 0)
                     || ' en ' || coalesce(sum(cantidad), 0) || ' bultos' end
    from movimientos_stock where anulado_el is null and tipo = 'stock_inicial'

    union all
    select 9, '09 - La plata de las cajas armadas',
           case when coalesce(sum(costo_total), 0) = 437215.92 and count(*) = 2
                then 'OK - $437.215,92 en 2 guías (328.125,00 + 109.090,92)'
                else 'FALLA: ' || count(*) || ' guías por $' || coalesce(sum(costo_total), 0) end
    from reprocesos where anulado_el is null and tipo = 'inicial'

    union all
    select 10, '10 - Los reprocesos iniciales producen sin consumir',
           case when count(*) = 0 then 'OK - bultos_tomados en cero, sin consumos'
                else 'FALLA: ' || count(*) || ' guías iniciales con toma o consumos' end
    from reprocesos r
    where r.tipo = 'inicial'
      and (r.bultos_tomados <> 0 or r.bultos_segunda <> 0 or r.bultos_merma <> 0
           or exists (select 1 from reprocesos_consumos rc where rc.reproceso_id = r.id))

    union all
    select 11, '11 - El FIFO arranca limpio: lo único con resto es lo del corte',
           coalesce('FALLA: ' || string_agg(f.tipo_lote || ' #' || f.origen_id
                                            || ' con ' || f.restante, ', '),
                    'OK - ningún lote viejo quedó con resto')
    from corte_fifo f
    where f.restante > 0
      and not (f.tipo_lote = 'stock_inicial'
               or (f.tipo_lote = 'reproceso'
                   and exists (select 1 from reprocesos r
                               where r.id = f.origen_id and r.tipo = 'inicial')))

    union all
    select 12, '12 - Ningún lote con resto quedó sin precio',
           coalesce('FALLA: ' || string_agg(tipo_lote || ' #' || origen_id, ', '),
                    'OK - todo lo que queda en el piso tiene costo')
    from corte_fifo where restante > 0 and costo_bulto is null

    union all
    select 100 + row_number() over (order by v.stock desc, e.nombre),
           'FOTO - ' || e.nombre,
           e.sueltos || ' sueltos + ' || (v.stock - e.sueltos) || ' cajas = ' || v.stock
    from corte_esperado e join corte_stock_vivo v on v.articulo_id = e.articulo_id
) todo
order by n;
