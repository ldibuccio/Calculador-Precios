-- ############################################################################
-- CORTE DEL MODELO — SEGUNDA VUELTA. FRUTAMAX Y SOLO FRUTAMAX.
--
-- Palmala NO lleva stock todavía y va a arrancar limpia cuando se implemente:
-- nada de esto se corre ahí.
--
-- ESTE ARCHIVO NO SE CORRE DE UNA. Es una lista de BLOQUES, cada uno pensado
-- para pegarse SOLO en el editor de Supabase, en orden, mirando el resultado
-- antes de pasar al siguiente. Ninguno pasa los 2500 caracteres, ninguno usa
-- tablas ni vistas temporales, y cada uno es UNA sentencia `do` (atómica de
-- verdad) más UNA consulta final que devuelve filas.
--
-- Reemplaza a db/corte_frutamax_puesta_a_cero_y_carga.sql, que NO se puede
-- reusar: usaba vistas temporales entre sentencias y el 29/08 terminó con
-- error habiendo escrito igual. Salió bien de casualidad.
--
-- LA FECHA DEL CORTE SE ESCRIBE EN UN SOLO LUGAR: el BLOQUE 1. Todos los
-- demás la leen de corte_modelo. Es la misma regla que el piso de fecha del
-- reproceso en crear_reproceso().
--
-- El procedimiento paso a paso, con qué mirar entre bloque y bloque, está en
-- docs/procedimiento_corte.md. Leerlo ANTES.
--
-- Verificado el 04/09/2026 contra Postgres 16 descartable cargado con
-- db/esquema_completo.sql y datos de prueba (base borrada al terminar):
-- corrida limpia 0-1-2-3-0-4-5-6-7, y después D0-D1 que deja todo como estaba.
-- Probados también los caminos de error: totales que no dan, bloque repetido,
-- deshacer fuera de orden.
-- ############################################################################

-- ===========================================================================
-- BLOQUE 0 — LA FOTO DE ANTES. Solo lectura, no escribe nada.
-- Es el stock vivo por artículo, con las SEIS PATAS separadas, tal como lo
-- calcula stock_deposito_por_articulo(). Guardá el resultado: es contra esto
-- que se compara todo lo que sigue.
with vig as (
  select distinct on (cliente_id, fecha_operacion) id from pedidos
  where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
sal as (
  select r.articulo_id a, sum(coalesce(r.cantidad_armada, r.cantidad)) t
  from pedidos_renglones r join vig v on v.id = r.pedido_id
  where r.armado_el is not null and r.anulado_el is null and r.articulo_id is not null
  group by 1),
ent as (
  select articulo_id a, sum(cantidad_cajones_real) t from compras
  where estado = 'recepcionado' group by 1),
rei as (
  select articulo_id a, sum(cantidad) t from movimientos_stock
  where anulado_el is null and tipo = 'reingreso_rechazo'
    and (destino_rechazo is null or destino_rechazo = 'stock') group by 1),
aju as (
  select articulo_id a, sum(cantidad) t from movimientos_stock
  where anulado_el is null and tipo <> 'reingreso_rechazo' group by 1),
rep as (
  select articulo_id a, sum(bultos_primera) e, sum(bultos_tomados) s
  from reprocesos where anulado_el is null group by 1)
select ar.id, ar.nombre,
  coalesce(ent.t,0) compras, coalesce(rei.t,0) reingresos, coalesce(aju.t,0) ajustes,
  coalesce(rep.e,0) primera, coalesce(rep.s,0) tomados, coalesce(sal.t,0) armado,
  coalesce(ent.t,0)+coalesce(rei.t,0)+coalesce(aju.t,0)
  +coalesce(rep.e,0)-coalesce(rep.s,0)-coalesce(sal.t,0) stock
from articulos ar
left join ent on ent.a=ar.id left join sal on sal.a=ar.id
left join rei on rei.a=ar.id left join aju on aju.a=ar.id
left join rep on rep.a=ar.id
order by 9 desc, 2;

-- ===========================================================================
-- BLOQUE 1 — MOVER LA FECHA DE CORTE.
-- ES EL ÚNICO LUGAR DONDE SE ESCRIBE LA FECHA NUEVA. Todos los bloques que
-- siguen la leen de corte_modelo, así que no hay que cambiarla en ningún
-- otro lado. Cambiá el 2026-09-06 por el día real del corte y nada más.
-- ANTES DE CORRER ESTO: ya tienen que estar cargadas TODAS las guías R
-- pendientes con su fecha vieja. Después de este bloque el piso las rechaza.
do $$
declare vieja date; nueva date := date '2026-09-06';
begin
  select fecha into vieja from corte_modelo where id = 1;
  if vieja is null then
    raise exception 'No hay fila en corte_modelo: la base esta a medio configurar.';
  end if;
  if nueva <= vieja then
    raise exception 'La fecha nueva (%) no es posterior a la vigente (%).', nueva, vieja;
  end if;
  if nueva > current_date + 1 then
    raise exception 'La fecha nueva (%) esta demasiado adelante.', nueva;
  end if;
  update corte_modelo set fecha = nueva where id = 1;
end $$;

select fecha as corte_vigente from corte_modelo where id = 1;

-- ===========================================================================
-- BLOQUE 2 — SACADO EL 05/09/2026. NO SE CORRE. El número queda vacío a
-- propósito, para que no se confunda con el bloque 2 del corte anterior.
--
-- Nuleaba `reprocesos.ficha_id` de las guías R anteriores al corte. Existía
-- porque la cuenta por ficha (`_SQL_STOCK_PARTIDO`) no tenía fecha y las
-- cajas viejas seguían contando como disponibles. Era un parche de DATOS
-- para un agujero de CONSULTA, y encima medio parche: sacaba las entradas
-- y dejaba las salidas, porque no tocaba `pedidos_renglones.ficha_id`. Ese
-- es exactamente el negativo estructural que encontramos el 04/09, y el
-- compensatorio no lo alcanza (es por ARTÍCULO; esta cuenta no lee
-- movimientos).
--
-- Medido antes de sacarlo, simulando este corte: Pepino -145 -> -245,
-- Zapallito +5 -> -30, Perita 0 -> -12. Las fichas sanas terminaban
-- negativas, y cuanto más tarde el corte más semana de guías R buenas se
-- llevaba puesta.
--
-- Lo reemplaza el PISO DE FECHA en `_SQL_STOCK_PARTIDO`: las dos patas
-- desde el corte inclusive. Con eso el resultado es el mismo con el bloque
-- corrido o sin correr (verificado en las dos direcciones), así que lo
-- único que aportaba era destruir la ficha de guías R viejas — un dato que
-- no se recupera y que es la única forma de saber para qué ficha se armó
-- cada guía.
--
-- Y el respaldo `corte_respaldo_fichas_reprocesos` no se toca: sigue
-- guardando lo que nuleó el corte del 31/08, y el D0 lo sigue usando.

-- ===========================================================================
-- BLOQUE 3 — EL COMPENSATORIO. Un movimiento por artículo con stock <> 0,
-- por -1 × las seis patas leídas en el momento: ningún número a mano. Fecha:
-- el día ANTERIOR al corte, para que en el FIFO quede antes del stock inicial.
do $$
declare corte date; n int;
begin
  select fecha into corte from corte_modelo where id = 1;
  if exists (select 1 from movimientos_stock
             where tipo='cierre_modelo_viejo' and fecha_operacion=corte-1) then
    raise exception 'El compensatorio de este corte ya se corrio.';
  end if;
  insert into movimientos_stock
    (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema)
  with vig as (
    select distinct on (cliente_id, fecha_operacion) id from pedidos
    where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
  sal as (
    select r.articulo_id a, sum(coalesce(r.cantidad_armada, r.cantidad)) t
    from pedidos_renglones r join vig v on v.id=r.pedido_id
    where r.armado_el is not null and r.anulado_el is null
      and r.articulo_id is not null group by 1),
  ent as (select articulo_id a, sum(cantidad_cajones_real) t from compras
    where estado='recepcionado' group by 1),
  rei as (select articulo_id a, sum(cantidad) t from movimientos_stock
    where anulado_el is null and tipo='reingreso_rechazo'
      and (destino_rechazo is null or destino_rechazo='stock') group by 1),
  aju as (select articulo_id a, sum(cantidad) t from movimientos_stock
    where anulado_el is null and tipo<>'reingreso_rechazo' group by 1),
  rep as (select articulo_id a, sum(bultos_primera) e, sum(bultos_tomados) s
    from reprocesos where anulado_el is null group by 1),
  vivo as (select ar.id, coalesce(ent.t,0)+coalesce(rei.t,0)+coalesce(aju.t,0)
      +coalesce(rep.e,0)-coalesce(rep.s,0)-coalesce(sal.t,0) st
    from articulos ar
    left join ent on ent.a=ar.id left join sal on sal.a=ar.id
    left join rei on rei.a=ar.id left join aju on aju.a=ar.id
    left join rep on rep.a=ar.id)
  select id, 'cierre_modelo_viejo', -st,
         'Cierre del modelo viejo (corte '||corte||')', corte-1, st
  from vivo where st <> 0;
  get diagnostics n = row_count;
  if n = 0 then
    raise exception 'No se compenso ningun articulo: revisa el bloque 0.';
  end if;
end $$;

select count(*) compensados, sum(cantidad) suma
from movimientos_stock where tipo='cierre_modelo_viejo'
  and fecha_operacion=(select fecha from corte_modelo where id=1)-1;

-- ===========================================================================
-- BLOQUE 4 — EL STOCK INICIAL (los bultos SUELTOS contados en el piso).
-- Una fila por artículo: (id, nombre, bultos, costo). El nombre va en el
-- JOIN: un id que apunte a otro artículo no entra, y el conteo de abajo
-- hace fallar el bloque entero sin escribir nada.
-- PONÉ en 'esperados' la cantidad de filas DE ESTE BLOQUE.
-- SI NO ENTRA EN 2500 CARACTERES: partilo en dos y corré los dos, cada uno
-- con su propio 'esperados'. El orden no importa; el total lo valida el 5.
do $$
declare corte date; esperados int := 0;  -- filas DE ESTE bloque
        n int;
begin
  select fecha into corte from corte_modelo where id = 1;
  if not exists (select 1 from movimientos_stock
                 where tipo='cierre_modelo_viejo' and fecha_operacion=corte-1) then
    raise exception 'Falta el bloque 3: sin compensatorio esto duplica.'; end if;

  insert into movimientos_stock (articulo_id, tipo, cantidad, motivo,
                                 fecha_operacion, stock_sistema, costo_por_bulto)
  select f.aid, 'stock_inicial', f.bultos, 'Stock inicial del corte ('||corte||')',
         corte, 0, f.costo
  from (values
    -- REEMPLAZAR POR LO CONTADO. Estas tres filas son solo la forma.
    -- Con 18 filas el bloque queda en unos 2300 caracteres: entra.
    (29,'Morron Rojo',44::numeric,33000::numeric),
    (15,'Tomate Redondo',89,43846.15),
    (18,'Pepino',33,23857.14)
  ) as f(aid, nom, bultos, costo)
  join articulos a on a.id=f.aid and a.nombre=f.nom
  where f.bultos > 0
    and not exists (select 1 from movimientos_stock m
                    where m.tipo='stock_inicial' and m.fecha_operacion=corte
                      and m.articulo_id=f.aid);
  get diagnostics n = row_count;
  if n <> esperados then
    raise exception 'Entraron % de %: hay un id, un nombre o un repetido.', n, esperados;
  end if;
end $$;

select count(*) articulos, sum(cantidad) bultos
from movimientos_stock where tipo='stock_inicial'
  and fecha_operacion=(select fecha from corte_modelo where id=1);

-- ===========================================================================
-- BLOQUE 5 — CIERRE DEL STOCK INICIAL. Lee lo que quedó escrito y lo compara
-- con los totales de la planilla. Si no dan, FALLA y no toca nada: para
-- corregir se corre el bloque D4 (deshacer el 4), se arregla la lista y se
-- vuelve a correr el 4. Ojo: un `raise` adentro de un `do` deshace también lo
-- que ese mismo bloque hubiera borrado, así que el borrado va aparte.
do $$
declare corte date; esperados int := 0; bultos_esp numeric := 0;
        plata_esp numeric := 0;  -- LOS TRES TOTALES DE LA PLANILLA
        n int; b numeric; p numeric;
begin
  select fecha into corte from corte_modelo where id = 1;
  select count(*), coalesce(sum(cantidad),0),
         coalesce(round(sum(cantidad*costo_por_bulto),2),0) into n, b, p
  from movimientos_stock where tipo='stock_inicial' and fecha_operacion=corte;
  if n <> esperados or b <> bultos_esp or p <> plata_esp then
    raise exception 'Cargado: % articulos, % bultos, %. Planilla: %, %, %. Corre el D4 y repeti el 4.',
      n, b, p, esperados, bultos_esp, plata_esp;
  end if;
end $$;

select count(*) articulos, sum(cantidad) bultos,
       round(sum(cantidad*costo_por_bulto),2) plata
from movimientos_stock where tipo='stock_inicial'
  and fecha_operacion=(select fecha from corte_modelo where id=1);

-- ===========================================================================
-- BLOQUE 6 — LAS CAJAS YA ARMADAS que había en el piso, como guías R
-- 'inicial': PRODUCEN SIN CONSUMIR (bultos_tomados = 0), porque los cajones
-- que las originaron no se van a cargar nunca. Una fila por FICHA:
-- (ficha_id, cajas, costo por caja). El artículo y el cliente salen de la
-- ficha, no se escriben. MERCADERÍA SOLA, SIN CARTÓN: el envase se suma río
-- abajo en la cotización y en la Rentabilidad Real; acá lo contaría dos veces.
do $$
declare corte date; esperados int := 0;  -- filas de la lista
        n int;
begin
  select fecha into corte from corte_modelo where id = 1;
  if exists (select 1 from reprocesos where tipo='inicial' and fecha_operacion=corte) then
    raise exception 'Las cajas armadas de este corte ya se cargaron.'; end if;
  if not exists (select 1 from movimientos_stock
                 where tipo='stock_inicial' and fecha_operacion=corte) then
    raise exception 'Falta el bloque 4: carga primero los sueltos.'; end if;

  insert into reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                          bultos_segunda, bultos_merma, costo_total,
                          costo_por_bulto_primera, cliente_id, ficha_id, tipo)
  select fl.articulo_id, corte, 0, v.cajas, 0, 0,
         round(v.cajas*v.costo, 2), v.costo, fl.cliente_id, fl.id, 'inicial'
  from (values
    -- REEMPLAZAR POR LO CONTADO: (ficha_id, cajas, costo por caja).
    (5, 25::numeric, 13125::numeric),
    (7, 12, 9090.91)
  ) as v(ficha_id, cajas, costo)
  join fichas_logistica fl on fl.id = v.ficha_id
  where v.cajas > 0;

  get diagnostics n = row_count;
  if n <> esperados then
    raise exception 'Entraron % de %: hay una ficha_id que no existe.', n, esperados;
  end if;
end $$;

select r.id, a.nombre articulo, coalesce(fl.nombre_cliente, a.nombre) ficha,
       c.nombre cliente, r.bultos_primera cajas, r.costo_por_bulto_primera costo
from reprocesos r
join articulos a on a.id = r.articulo_id
join fichas_logistica fl on fl.id = r.ficha_id
left join clientes c on c.id = r.cliente_id
where r.tipo='inicial' and r.fecha_operacion=(select fecha from corte_modelo where id=1)
order by 2;

-- ===========================================================================
-- BLOQUE 6B — LA SEGUNDA QUE ESTÁ EN EL PISO. Nuevo, no estaba en el corte
-- anterior. Entra como guía R 'inicial' con bultos_primera = 0 y la segunda
-- en bultos_segunda: es la única puerta al pool de segunda que no es un
-- rechazo de cliente.
-- SIN FICHA Y SIN CLIENTE a propósito: es descarte para el puesto.
-- costo_total = 0 y NO NULL: en el modelo la segunda vale cero (todo el
-- costo va a la primera), y un NULL prendería la alerta "guías R con costo
-- incompleto" con casos que no se pueden completar nunca.
-- costo_por_bulto_primera queda NULL porque no hubo primera.
do $$
declare corte date; esperados int := 0;  -- filas de la lista
        n int;
begin
  select fecha into corte from corte_modelo where id = 1;
  if exists (select 1 from reprocesos
             where tipo='inicial' and fecha_operacion=corte and bultos_primera = 0) then
    raise exception 'La segunda de este corte ya se cargo.'; end if;

  insert into reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                          bultos_segunda, bultos_merma, costo_total,
                          costo_por_bulto_primera, cliente_id, ficha_id, tipo)
  select a.id, corte, 0, 0, v.cajas, 0, 0, null, null, null, 'inicial'
  from (values
    -- REEMPLAZAR POR LO CONTADO: (nombre del artículo, cajas de segunda).
    ('Zapallito', 15::numeric),
    ('Limon', 3)
  ) as v(nom, cajas)
  join articulos a on a.nombre = v.nom
  where v.cajas > 0;

  get diagnostics n = row_count;
  if n <> esperados then
    raise exception 'Entraron % de %: hay un nombre de articulo que no coincide.', n, esperados;
  end if;
end $$;

-- El pool de segunda que queda: lo cargado ahora y el total del artículo.
select a.nombre articulo, r.bultos_segunda cargada,
       (select coalesce(sum(r2.bultos_segunda),0) from reprocesos r2
        where r2.anulado_el is null and r2.articulo_id = r.articulo_id) pool_total
from reprocesos r
join articulos a on a.id = r.articulo_id
where r.tipo='inicial' and r.bultos_primera = 0
  and r.fecha_operacion=(select fecha from corte_modelo where id=1)
order by 1;

-- ===========================================================================
-- BLOQUE 7 — VERIFICADOR FINAL. Solo lectura. El stock de cada artículo
-- tiene que ser exactamente lo contado: sueltos + cajas armadas. La columna
-- 'dif' tiene que dar 0 en TODAS las filas. Cualquier otra cosa se mira
-- antes de abrir el depósito.
with vig as (
  select distinct on (cliente_id, fecha_operacion) id from pedidos
  where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
sal as (
  select r.articulo_id a, sum(coalesce(r.cantidad_armada, r.cantidad)) t
  from pedidos_renglones r join vig v on v.id=r.pedido_id
  where r.armado_el is not null and r.anulado_el is null
    and r.articulo_id is not null group by 1),
ent as (select articulo_id a, sum(cantidad_cajones_real) t from compras
  where estado='recepcionado' group by 1),
rei as (select articulo_id a, sum(cantidad) t from movimientos_stock
  where anulado_el is null and tipo='reingreso_rechazo'
    and (destino_rechazo is null or destino_rechazo='stock') group by 1),
aju as (select articulo_id a, sum(cantidad) t from movimientos_stock
  where anulado_el is null and tipo<>'reingreso_rechazo' group by 1),
rep as (select articulo_id a, sum(bultos_primera) e, sum(bultos_tomados) s
  from reprocesos where anulado_el is null group by 1),
cargado as (
  select articulo_id a, sum(cantidad) t from movimientos_stock
  where tipo='stock_inicial'
    and fecha_operacion=(select fecha from corte_modelo where id=1) group by 1),
cajas as (
  select articulo_id a, sum(bultos_primera) t from reprocesos
  where tipo='inicial'
    and fecha_operacion=(select fecha from corte_modelo where id=1) group by 1)
select ar.nombre,
  coalesce(cargado.t,0) sueltos, coalesce(cajas.t,0) cajas_armadas,
  coalesce(ent.t,0)+coalesce(rei.t,0)+coalesce(aju.t,0)
  +coalesce(rep.e,0)-coalesce(rep.s,0)-coalesce(sal.t,0) stock,
  coalesce(ent.t,0)+coalesce(rei.t,0)+coalesce(aju.t,0)
  +coalesce(rep.e,0)-coalesce(rep.s,0)-coalesce(sal.t,0)
  -coalesce(cargado.t,0)-coalesce(cajas.t,0) dif
from articulos ar
left join ent on ent.a=ar.id left join sal on sal.a=ar.id
left join rei on rei.a=ar.id left join aju on aju.a=ar.id
left join rep on rep.a=ar.id
left join cargado on cargado.a=ar.id left join cajas on cajas.a=ar.id
order by 5 desc, 1;

-- ===========================================================================
-- BLOQUE D0 — DESHACER EL CORTE ENTERO. Para "salió mal el mismo día", NO
-- para deshacer operación: si ya se cargó algo del lado nuevo se corta.
-- Las fichas que devuelve son SOLO las que respaldó este corte (guardado_el
-- de los últimos 2 días). NO devuelve corte_modelo.fecha: eso es el D1.
do $$
declare corte date; hubo text; tz text := 'America/Argentina/Buenos_Aires';
begin
  select fecha into corte from corte_modelo where id = 1;
  select string_agg(q, ', ') into hubo from (
    select 'guias R del '||fecha_operacion q from reprocesos
    where tipo='normal' and anulado_el is null and fecha_operacion >= corte
    union all
    select 'movimientos del '||fecha_operacion from movimientos_stock
    where anulado_el is null and fecha_operacion >= corte
      and tipo not in ('cierre_modelo_viejo','stock_inicial')
    union all
    select 'compras del '||(procesada_el at time zone tz)::date from compras
    where estado='recepcionado' and (procesada_el at time zone tz)::date >= corte
    union all
    select 'armados del '||(armado_el at time zone tz)::date from pedidos_renglones
    where armado_el is not null and anulado_el is null
      and (armado_el at time zone tz)::date >= corte) t;
  if hubo is not null then
    raise exception 'YA HAY OPERACION DESPUES DEL CORTE (%). Se decide a mano.', hubo;
  end if;

  delete from reprocesos_consumos where reproceso_id in
    (select id from reprocesos where tipo='inicial' and fecha_operacion=corte);
  delete from reprocesos where tipo='inicial' and fecha_operacion=corte;
  delete from movimientos_stock where tipo='stock_inicial' and fecha_operacion=corte;
  delete from movimientos_stock
   where tipo='cierre_modelo_viejo' and fecha_operacion=corte-1;
  update reprocesos r set ficha_id = b.ficha_id
    from corte_respaldo_fichas_reprocesos b
   where b.reproceso_id = r.id and b.guardado_el > now() - interval '2 days';
  delete from corte_respaldo_fichas_reprocesos
   where guardado_el > now() - interval '2 days';
end $$;

select
 (select count(*) from movimientos_stock
   where tipo in ('stock_inicial','cierre_modelo_viejo')
     and fecha_operacion >= (select fecha from corte_modelo where id=1)-1) movs,
 (select count(*) from reprocesos where tipo='inicial'
   and fecha_operacion=(select fecha from corte_modelo where id=1)) cajas;

-- ===========================================================================
-- BLOQUE D1 — DEVOLVER LA FECHA DE CORTE. Se corre DESPUÉS del D0, nunca
-- antes: el D0 borra buscando por la fecha vigente. Poné la fecha vieja.
do $$
declare vieja date := date '2026-08-31';
begin
  if exists (select 1 from movimientos_stock
             where tipo in ('stock_inicial','cierre_modelo_viejo')
               and fecha_operacion >= vieja + 1) then
    raise exception 'Todavia hay movimientos del corte nuevo: corre el D0 primero.';
  end if;
  update corte_modelo set fecha = vieja where id = 1;
end $$;

select fecha as corte_vigente from corte_modelo where id = 1;

-- ===========================================================================
-- BLOQUE D4 — DESHACER EL 4. Borra el stock inicial de ESTE corte y nada más.
-- Se corre solo si el bloque 5 dijo que los totales no dan. No toca el
-- compensatorio (bloque 3) ni las cajas armadas (bloque 6).
do $$
declare corte date;
begin
  select fecha into corte from corte_modelo where id = 1;
  if exists (select 1 from reprocesos where tipo='inicial' and fecha_operacion=corte) then
    raise exception 'Ya se cargaron las cajas armadas (bloque 6): borra esas primero.';
  end if;
  delete from movimientos_stock where tipo='stock_inicial' and fecha_operacion=corte;
end $$;

select count(*) quedan_stock_inicial
from movimientos_stock where tipo='stock_inicial'
  and fecha_operacion=(select fecha from corte_modelo where id=1);

