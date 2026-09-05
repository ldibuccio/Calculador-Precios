-- ############################################################################
-- QUÉ GUÍAS R FALTAN — PARA EL PASO 0 DEL CORTE. Solo lectura, no escribe.
--
-- Tres consultas. Se pegan por separado; ninguna pasa los 2500 caracteres.
--
-- LAS DOS PRIMERAS ESTÁN ACOTADAS, y los dos recortes los pidió el dueño:
--   * DESDE la fecha de corte vigente inclusive. Lo anterior lo trató el
--     compensatorio del corte pasado y no se corrige — Decisiones
--     confirmadas, punto 7.
--   * SOLO artículos con al menos una guía R en el período. Los que nunca se
--     reprocesan no tienen ninguna guía que reconstruir; su déficit por ficha
--     es otra cosa (el formato de la ficha, E5).
--
-- OJO CON QUÉ NÚMERO ES CADA COSA. Estas consultas NO calculan el `sin_lote`
-- del FIFO (los 88 de Pepino, los 109 de Zapallito). Ese sale de
-- `repartir_fifo` en core/stock.py, que camina las salidas en orden y no deja
-- que un lote posterior tape una salida anterior — reescribir eso en SQL
-- sería tener la regla escrita dos veces, y esta es justo la vez en que más
-- caro saldría: el depósito trabajaría de una lista que no coincide con lo
-- que el sistema después calcula.
--
-- Lo que dan es la cuenta POR FICHA (la 2), que es la que contesta la
-- pregunta operativa: qué guía R reconstruir, de qué ficha, cuántas cajas y
-- de qué día. Los dos números no tienen por qué coincidir y no es un error:
-- son cuentas distintas (ver el mapa de las tres cuentas en
-- docs/diseno_base_datos.md).
-- ############################################################################

-- ===========================================================================
-- QUÉ GUÍAS R FALTAN. Solo lectura. Acotada al período POST-CORTE y a los
-- artículos que de verdad se reprocesan.
--   * DESDE la fecha de corte inclusive: lo anterior lo trató el
--     compensatorio del corte pasado y no se corrige (Decisiones
--     confirmadas, punto 7).
--   * SOLO artículos con al menos una guía R en el período: los que nunca se
--     reprocesan no tienen ninguna guía que reconstruir, y su déficit por
--     ficha es otra cosa (el formato de la ficha, E5).
with corte as (select fecha d from corte_modelo where id = 1),
vig as (
  select distinct on (cliente_id, fecha_operacion) id from pedidos
  where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
con_guias as (
  select distinct r.articulo_id ai from reprocesos r, corte
  where r.anulado_el is null and r.fecha_operacion >= corte.d),
mov as (
  select r.articulo_id ai, r.ficha_id fi, r.fecha_operacion f, r.bultos_primera c
  from reprocesos r, corte
  where r.anulado_el is null and r.ficha_id is not null and r.fecha_operacion >= corte.d
  union all
  select pr.articulo_id, pr.ficha_id,
         (pr.armado_el at time zone 'America/Argentina/Buenos_Aires')::date,
         -coalesce(pr.cantidad_armada, pr.cantidad)
  from pedidos_renglones pr join vig v on v.id = pr.pedido_id, corte
  where pr.armado_el is not null and pr.anulado_el is null
    and pr.articulo_id is not null and pr.ficha_id is not null
    and (pr.armado_el at time zone 'America/Argentina/Buenos_Aires')::date >= corte.d),
acum as (
  select ai, fi, f, c,
         sum(c) over (partition by ai, fi order by f, c desc
                      rows unbounded preceding) saldo
  from mov where ai in (select ai from con_guias))
select a.nombre articulo,
       coalesce(nullif(btrim(fl.nombre_cliente),''), a.nombre) ficha,
       cl.nombre cliente,
       min(case when acum.saldo < 0 then acum.f end) primer_dia_en_rojo,
       -min(acum.saldo) cajas_que_faltan,
       sum(case when acum.c < 0 then -acum.c else 0 end) cajas_salidas,
       sum(case when acum.c > 0 then acum.c else 0 end) cajas_producidas,
       case when sum(acum.c) >= 0
            then 'FECHA MAL: la guia R existe, corregir su fecha'
            else 'FALTA CARGAR: ' || (-sum(acum.c)) || ' cajas' end que_hacer
from acum
join articulos a on a.id = acum.ai
join fichas_logistica fl on fl.id = acum.fi
left join clientes cl on cl.id = fl.cliente_id
group by 1, 2, 3
having min(acum.saldo) < 0
order by 5 desc, 1;

-- ===========================================================================
-- CUÁNTAS SON. El mismo recorte que la consulta de arriba, contado.
-- Es el número que decide si el PASO 0 es viable o se salta.
--   * DESDE la fecha de corte inclusive: lo anterior lo trató el
--     compensatorio del corte pasado y no se corrige (Decisiones
--     confirmadas, punto 7).
--   * SOLO artículos con al menos una guía R en el período: los que nunca se
--     reprocesan no tienen ninguna guía que reconstruir, y su déficit por
--     ficha es otra cosa (el formato de la ficha, E5).
with corte as (select fecha d from corte_modelo where id = 1),
vig as (
  select distinct on (cliente_id, fecha_operacion) id from pedidos
  where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
con_guias as (
  select distinct r.articulo_id ai from reprocesos r, corte
  where r.anulado_el is null and r.fecha_operacion >= corte.d),
mov as (
  select r.articulo_id ai, r.ficha_id fi, r.fecha_operacion f, r.bultos_primera c
  from reprocesos r, corte
  where r.anulado_el is null and r.ficha_id is not null and r.fecha_operacion >= corte.d
  union all
  select pr.articulo_id, pr.ficha_id,
         (pr.armado_el at time zone 'America/Argentina/Buenos_Aires')::date,
         -coalesce(pr.cantidad_armada, pr.cantidad)
  from pedidos_renglones pr join vig v on v.id = pr.pedido_id, corte
  where pr.armado_el is not null and pr.anulado_el is null
    and pr.articulo_id is not null and pr.ficha_id is not null
    and (pr.armado_el at time zone 'America/Argentina/Buenos_Aires')::date >= corte.d),
acum as (
  select ai, fi, f, c,
         sum(c) over (partition by ai, fi order by f, c desc
                      rows unbounded preceding) saldo
  from mov where ai in (select ai from con_guias)),
por_ficha as (
  select acum.ai, acum.fi,
         min(acum.saldo) peor, sum(acum.c) neto
  from acum group by 1, 2 having min(acum.saldo) < 0)
select count(*) pares_en_rojo,
       count(*) filter (where neto < 0) a_reconstruir,
       count(*) filter (where neto >= 0) solo_corregir_la_fecha,
       coalesce(-sum(neto) filter (where neto < 0), 0) cajas_a_reconstruir
from por_ficha;

-- ===========================================================================
-- EL DÍA A DÍA DE UN ARTÍCULO. Solo lectura. Cambiá el nombre de abajo.
-- Muestra todo lo que entró y salió, en orden, con el saldo corriendo.
-- Sirve para ver el hueco a ojo: el día en que el saldo se va abajo de cero
-- es el día de la guía R que falta. Incluye las guías R SIN ficha, que la
-- otra consulta no ve.
with vig as (
  select distinct on (cliente_id, fecha_operacion) id from pedidos
  where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
mov as (
  select c.articulo_id ai,
         (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date f,
         'compra recibida' que, c.cantidad_cajones_real::numeric c, p.nombre det
  from compras c join proveedores p on p.id = c.proveedor_id
  where c.estado = 'recepcionado'
  union all
  select m.articulo_id, m.fecha_operacion, m.tipo, m.cantidad, m.motivo
  from movimientos_stock m where m.anulado_el is null
    and (m.destino_rechazo is null or m.destino_rechazo = 'stock'
         or m.tipo <> 'reingreso_rechazo')
  union all
  select r.articulo_id, r.fecha_operacion, 'guia R'||r.id||' primera',
         r.bultos_primera, coalesce(fl.nombre_cliente, 'sin ficha')
  from reprocesos r left join fichas_logistica fl on fl.id = r.ficha_id
  where r.anulado_el is null and r.bultos_primera > 0
  union all
  select r.articulo_id, r.fecha_operacion, 'guia R'||r.id||' tomo',
         -r.bultos_tomados, ''
  from reprocesos r where r.anulado_el is null and r.bultos_tomados > 0
  union all
  select pr.articulo_id,
         (pr.armado_el at time zone 'America/Argentina/Buenos_Aires')::date,
         'armado', -coalesce(pr.cantidad_armada, pr.cantidad),
         coalesce(fl.nombre_cliente, 'sin ficha')||' '||coalesce(pr.sucursal,'')
  from pedidos_renglones pr join vig v on v.id = pr.pedido_id
  left join fichas_logistica fl on fl.id = pr.ficha_id
  where pr.armado_el is not null and pr.anulado_el is null and pr.articulo_id is not null)
select mov.f fecha, mov.que, mov.c cantidad, mov.det detalle,
       sum(mov.c) over (order by mov.f, mov.c desc rows unbounded preceding) saldo
from mov join articulos a on a.id = mov.ai
where a.nombre ilike '%Pepino%'          -- <<< CAMBIAR ACÁ
order by mov.f, mov.c desc;
