-- ############################################################################
-- CORTE DEL 05/09/2026 — LOS DATOS REALES DEL CONTEO. Frutamax.
--
-- Es el REGISTRO de lo que se cargó, con los números del conteo físico ya
-- puestos. La plantilla de los bloques está en db/corte2_frutamax.sql.
--
-- Foto: 17 artículos, 264 bultos, $10.216.295,04. Todo lo que no está en la
-- lista del bloque 4 queda en cero.
-- Cajas armadas: 4 fichas de Día, 44 cajas, $543.697,65.
-- Segunda: Zapallito 15 y Limón 3, sin ficha y sin cliente.
--
-- Verificado el 05/09 contra Postgres 16 descartable con el esquema completo
-- y los nombres de artículo del conteo: los totales cierran, la guarda del
-- kilaje rechaza y no escribe, la segunda no toca el stock del artículo (el
-- verificador final sigue dando dif = 0 en todas las filas) y la alerta de
-- "guías R con costo incompleto" queda en cero.
-- ############################################################################

-- ===========================================================================
-- PREVIA AL BLOQUE 6 — las fichas de Día de esos cuatro artículos, con su
-- contenido por caja. Solo lectura. Es para confirmar el ficha_id Y que el
-- kilaje coincida ANTES de cargar: si no coincide, se para.
select fl.id ficha_id, a.nombre articulo,
       coalesce(nullif(btrim(fl.nombre_cliente),''), a.nombre) ficha,
       cl.nombre cliente, fl.contenido_caja, fl.unidad_venta,
       fl.envase_variable
from fichas_logistica fl
join articulos a on a.id = fl.articulo_id
join clientes cl on cl.id = fl.cliente_id
where a.nombre in ('Pomelo', 'Tomate Redondo', 'Berenjena', 'Lima')
order by a.nombre, fl.id;

-- ===========================================================================
-- BLOQUE 4 — EL STOCK INICIAL (los bultos SUELTOS contados en el piso).
-- 17 artículos, 264 bultos. Todo lo que no está acá queda en cero.
-- El nombre va en el JOIN: un id que apunte a otro artículo no entra, y el
-- conteo hace fallar el bloque entero sin escribir nada.
do $$
declare corte date; esperados int := 17; n int;
begin
  select fecha into corte from corte_modelo where id = 1;
  if not exists (select 1 from movimientos_stock
                 where tipo='cierre_modelo_viejo' and fecha_operacion=corte-1) then
    raise exception 'Falta el bloque 3: sin compensatorio esto duplica.'; end if;

  insert into movimientos_stock (articulo_id, tipo, cantidad, motivo,
                                 fecha_operacion, stock_sistema, costo_por_bulto)
  select a.id, 'stock_inicial', f.bultos, 'Stock inicial del corte ('||corte||')',
         corte, 0, f.costo
  from (values
    ('Mzn Red',10::numeric,55000::numeric),
    ('Tomate Perita',10,55000),
    ('Mzn Granny',35,60000),
    ('Pera',5,27000),
    ('Pomelo',16,10000),
    ('Zapallito',16,34019.61),
    ('Morron Rojo',27,45000),
    ('Morron Verde',12,29964.29),
    ('Tomate Redondo',30,47319.15),
    ('Pepino',20,27000),
    ('Tomate Cherry',5,25443.66),
    ('Mango',2,13000),
    ('Palta',22,64000),
    ('Lima',4,52000),
    ('Mandarina',20,10000),
    ('Ombligo',10,11361.70),
    ('Mzn Gob',20,28000)
  ) as f(nom, bultos, costo)
  join articulos a on a.nombre = f.nom
  where f.bultos > 0
    and not exists (select 1 from movimientos_stock m
                    where m.tipo='stock_inicial' and m.fecha_operacion=corte
                      and m.articulo_id=a.id);
  get diagnostics n = row_count;
  if n <> esperados then
    raise exception 'Entraron % de %: hay un nombre que no coincide o un repetido.', n, esperados;
  end if;
end $$;

select count(*) articulos, sum(cantidad) bultos
from movimientos_stock where tipo='stock_inicial'
  and fecha_operacion=(select fecha from corte_modelo where id=1);

-- ===========================================================================
-- BLOQUE 5 — CIERRE DEL STOCK INICIAL. Compara contra los tres totales de la
-- planilla. Si no dan, FALLA y no toca nada: se corre el D4, se corrige la
-- lista y se repite el 4.
do $$
declare corte date; esperados int := 17; bultos_esp numeric := 264;
        plata_esp numeric := 10216295.04;
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
-- BLOQUE 6 — LAS CAJAS YA ARMADAS, como guías R 'inicial': producen sin
-- consumir. (ficha_id, cajas, kg por caja, costo por caja).
-- EL KG VA EN EL JOIN: si no coincide con el contenido_caja de la ficha esa
-- fila no entra y el bloque falla entero. Es la verificación del kilaje,
-- adentro del bloque para que no se pueda saltear.
-- MERCADERÍA SOLA, SIN CARTÓN.
do $$
declare corte date; esperados int := 4; n int;
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
    -- REEMPLAZAR los ficha_id por los de la consulta previa.
    (101, 15::numeric, 16::numeric, 10000::numeric),   -- Pomelo caja Dia
    (102,  4, 16, 47319.15),                           -- Tomate Redondo caja Dia
    (103, 20,  4,  6800),                              -- Berenjena caja Dia
    (104,  5,  5, 13684.21)                            -- Lima caja Dia
  ) as v(ficha_id, cajas, kg, costo)
  join fichas_logistica fl on fl.id = v.ficha_id and fl.contenido_caja = v.kg
  where v.cajas > 0;

  get diagnostics n = row_count;
  if n <> esperados then
    raise exception 'Entraron % de %: una ficha_id no existe o su kg por caja no coincide.', n, esperados;
  end if;
end $$;

select r.id, a.nombre articulo, coalesce(fl.nombre_cliente, a.nombre) ficha,
       c.nombre cliente, r.bultos_primera cajas, r.costo_por_bulto_primera costo,
       fl.contenido_caja kg_caja
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
declare corte date; esperados int := 2; n int;
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
