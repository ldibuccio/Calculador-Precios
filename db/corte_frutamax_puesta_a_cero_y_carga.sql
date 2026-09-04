-- ############################################################################
-- REEMPLAZADO EL 04/09/2026 POR db/corte2_frutamax.sql. NO USAR ESTE.
-- Queda como registro de lo que se corrió el 29/08. El corte nuevo se hace
-- con el otro, y el paso a paso está en docs/procedimiento_corte.md.
-- ############################################################################

-- ############################################################################
-- ATENCIÓN — NO REUSAR ESTE SCRIPT COMO ESTÁ.
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

-- CORTE DEL MODELO — FRUTAMAX Y SOLO FRUTAMAX.
-- Puesta a cero del modelo viejo + carga del stock inicial del 31/08/2026.
-- Todo en UNA transacción: o entra completo o no entra nada.
-- Requiere db/agregar_cierre_modelo_viejo.sql aplicado antes.
--
-- El compensatorio NO usa números escritos a mano: se calcula como
-- -1 × (las seis patas del Stock del Sistema) leyendo el stock VIVO en el
-- momento de correrlo. Los artículos en negativo salen con compensatorio
-- POSITIVO solos, sin ninguna excepción en el código.

begin;

-- ---------------------------------------------------------------------------
-- LAS SEIS PATAS, UNA SOLA VEZ.
-- Vista temporal (se recalcula en cada referencia, así el paso 3 ve el efecto
-- del paso 2). Es exactamente la cuenta de stock_deposito_por_articulo():
-- compras recepcionadas + reingresos que quedan + ajustes/mermas/stock inicial
-- + primera de reprocesos − tomado por reprocesos − armado de pedidos vigentes.
-- ---------------------------------------------------------------------------
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
       coalesce(e.total, 0) as entradas,
       coalesce(s.total, 0) as salidas,
       coalesce(r.total, 0) as reingresos,
       coalesce(aj.total, 0) as ajustes,
       coalesce(rp.entradas, 0) as reproceso_primera,
       coalesce(rp.salidas, 0) as reproceso_tomados,
       coalesce(e.total, 0) + coalesce(r.total, 0) + coalesce(aj.total, 0)
       + coalesce(rp.entradas, 0) - coalesce(rp.salidas, 0) - coalesce(s.total, 0) as stock
from articulos a
left join entradas e on e.articulo_id = a.id
left join salidas s on s.articulo_id = a.id
left join reingresos r on r.articulo_id = a.id
left join ajustes aj on aj.articulo_id = a.id
left join reproc rp on rp.articulo_id = a.id;

-- ---------------------------------------------------------------------------
-- GUARDA 1 — ¿ES FRUTAMAX?
-- Los 18 artículos de la foto, con su id Y su nombre. En cualquier otra base
-- esos ids son otros artículos y el script se corta acá sin escribir nada.
-- ---------------------------------------------------------------------------
create temp table foto (articulo_id bigint primary key, nombre text,
                        bultos numeric, costo numeric) on commit drop;
insert into foto values
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

do $$
declare mal text;
begin
    select string_agg(f.articulo_id || ' esperaba "' || f.nombre
                      || '" y tiene "' || coalesce(a.nombre, '(no existe)') || '"', '; ')
      into mal
    from foto f left join articulos a on a.id = f.articulo_id
    where a.nombre is distinct from f.nombre;
    if mal is not null then
        raise exception 'NO ES FRUTAMAX (o cambiaron los nombres): %', mal;
    end if;
    if (select count(*) from foto) <> 18 or (select sum(bultos) from foto) <> 531 then
        raise exception 'La foto no es la aprobada: % artículos, % bultos',
            (select count(*) from foto), (select sum(bultos) from foto);
    end if;
    if (select round(sum(bultos * costo), 2) from foto) <> 17522615.76 then
        raise exception 'La foto no suma $17.522.615,76 sino %',
            (select round(sum(bultos * costo), 2) from foto);
    end if;
end $$;

-- ---------------------------------------------------------------------------
-- GUARDA 2 — ¿YA SE CORRIÓ? ¿ES LA FECHA QUE DICE LA BASE?
-- ---------------------------------------------------------------------------
do $$
begin
    if exists (select 1 from movimientos_stock where tipo = 'cierre_modelo_viejo') then
        raise exception 'YA HAY MOVIMIENTOS DE CIERRE: el corte ya se corrió. Corré el rollback antes de repetirlo.';
    end if;
    if exists (select 1 from movimientos_stock where tipo = 'stock_inicial') then
        raise exception 'YA HAY STOCK INICIAL CARGADO: revisá antes de repetir.';
    end if;
    if exists (select 1 from reprocesos where tipo = 'inicial') then
        raise exception 'YA HAY REPROCESOS INICIALES: revisá antes de repetir.';
    end if;
    if exists (select 1 from corte_respaldo_fichas_reprocesos) then
        raise exception 'YA HAY FICHAS RESPALDADAS: el corte ya tocó guías R. Corré el rollback antes de repetirlo.';
    end if;
    if (select fecha from corte_modelo where id = 1) is distinct from date '2026-08-31' then
        raise exception 'La fecha de corte de la base no es 2026-08-31 sino %',
            (select fecha from corte_modelo where id = 1);
    end if;
end $$;

-- ---------------------------------------------------------------------------
-- PASO 1 — EL AGUJERO DE LAS FICHAS
-- Las guías R pre-corte con ficha asignada (LIMON GRANEL 15 cajas y
-- MANDARINA G 38 cajas, las dos de Día) dejan de contar POR FICHA. No se
-- anulan: ocurrieron. Quedan como las otras 36 pre-corte, con ficha en NULL
-- = "dato viejo que no se completa". Sus cajas siguen contando en el total
-- del artículo, que el compensatorio lleva a cero.
-- ---------------------------------------------------------------------------
do $$
declare tocadas int; cajas numeric;
begin
    select count(*), coalesce(sum(bultos_primera), 0) into tocadas, cajas
    from reprocesos
    where anulado_el is null and ficha_id is not null
      and fecha_operacion < date '2026-08-31';
    if tocadas <> 2 or cajas <> 53 then
        raise exception 'Esperaba 2 guías R con ficha y 53 cajas (15 + 38); encontré % guías y % cajas',
            tocadas, cajas;
    end if;
end $$;

insert into corte_respaldo_fichas_reprocesos (reproceso_id, ficha_id)
select id, ficha_id from reprocesos
where anulado_el is null and ficha_id is not null
  and fecha_operacion < date '2026-08-31';

update reprocesos
set ficha_id = null
where anulado_el is null and ficha_id is not null
  and fecha_operacion < date '2026-08-31';

-- ---------------------------------------------------------------------------
-- PASO 2 — EL COMPENSATORIO, CALCULADO
-- Un movimiento por artículo con stock distinto de cero. cantidad =
-- -1 × las seis patas. stock_sistema = la foto del sistema SIN este
-- movimiento, igual que crear_movimiento_stock().
-- Fecha 30/08, el último día del modelo viejo: así el lote del compensatorio
-- de un artículo en negativo queda ANTES del stock inicial en el FIFO y se lo
-- come el excedente de salidas históricas, dejando intacto el lote costeado.
-- ---------------------------------------------------------------------------
insert into movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema)
select articulo_id, 'cierre_modelo_viejo', -stock,
       'Cierre del modelo viejo (corte 2026-08-31)', date '2026-08-30', stock
from corte_stock_vivo
where stock <> 0;

do $$
declare quedan text;
begin
    select string_agg(nombre || ' = ' || stock, ', ') into quedan
    from corte_stock_vivo where stock <> 0;
    if quedan is not null then
        raise exception 'Después del compensatorio quedó stock distinto de cero: %', quedan;
    end if;
end $$;

-- ---------------------------------------------------------------------------
-- PASO 3 — EL STOCK INICIAL (los sueltos)
-- Réplica exacta de crear_stock_inicial(): tipo propio, costo obligatorio,
-- fecha del corte, y stock_sistema = la foto SIN el movimiento (que después
-- del paso 2 es cero en los 18: el paso anterior ya lo verificó).
-- ---------------------------------------------------------------------------
insert into movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion,
                               stock_sistema, costo_por_bulto)
select f.articulo_id, 'stock_inicial', f.bultos,
       'Stock inicial del corte (2026-08-31)', date '2026-08-31',
       v.stock, f.costo
from foto f
join corte_stock_vivo v on v.articulo_id = f.articulo_id;

-- ---------------------------------------------------------------------------
-- PASO 4 — LAS CAJAS YA ARMADAS (reprocesos tipo 'inicial')
-- Réplica exacta de crear_reproceso_inicial(): bultos_tomados = 0 (producen
-- sin consumir), segunda y merma en cero, todo el costo a la primera, y el
-- cliente sale de la ficha (no se escribe a mano).
-- MERCADERÍA SOLA, SIN CARTÓN: el envase se suma río abajo en la cotización
-- y en la Rentabilidad Real; meterlo acá lo contaría dos veces.
-- ---------------------------------------------------------------------------
do $$
declare ok int;
begin
    select count(*) into ok from fichas_logistica
    where (id = 5 and articulo_id = 19) or (id = 7 and articulo_id = 17);
    if ok <> 2 then
        raise exception 'Las fichas 5 (Zapallito) y 7 (Berenjena) no son las esperadas';
    end if;
end $$;

insert into reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_total, costo_por_bulto_primera,
                        cliente_id, ficha_id, tipo)
select f.articulo_id, date '2026-08-31', 0, v.cajas, 0, 0,
       round(v.cajas * v.costo, 2), v.costo, f.cliente_id, f.id, 'inicial'
from (values (5, 25::numeric, 13125::numeric),
             (7, 12::numeric, 9090.91::numeric)) as v(ficha_id, cajas, costo)
join fichas_logistica f on f.id = v.ficha_id;

commit;
