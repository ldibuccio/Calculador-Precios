-- ¿Cuánto rechazo vuelve, y qué se hace hoy con él?
--
-- Dimensiona el cuarto destino (devolución al proveedor): si vuelven dos
-- por mes, alcanza con registrarlo; si vuelven veinte, conviene mirar
-- también la plata.
--
-- El destino nuevo TODAVÍA NO EXISTE, así que acá no puede aparecer: lo
-- que se mide es el hecho —mercadería que volvió— repartido por lo que se
-- hizo con ella hasta hoy. `destino NULL` son los reingresos viejos,
-- anteriores a que el destino existiera: quedaban en stock por definición.
--
-- CONTEOS y no lista. `ultimo_reingreso` es el testigo: sobre una base
-- parada todos los ceros son ciertos y ninguno informa (Palmala no vota).
--
-- `por_mes` sale del span REAL de los datos (primer a último reingreso),
-- no de un rango fijo: con dos meses de historia un promedio sobre doce
-- diría la cuarta parte.
--
-- Probada con el caso plantado (corolario 36): los contadores se mueven.

with r as (
  select * from movimientos_stock
  where tipo = 'reingreso_rechazo' and anulado_el is null
)
select
  (select max(fecha_operacion) from r) as ultimo_reingreso,
  (select min(fecha_operacion) from r) as primer_reingreso,
  (select count(*) from r) as reingresos,
  (select coalesce(sum(cantidad), 0) from r) as bultos,

  (select count(*) from r where destino_rechazo is null) as destino_viejo_null,
  (select count(*) from r where destino_rechazo = 'stock') as a_stock,
  (select count(*) from r where destino_rechazo = 'segunda') as a_segunda,
  (select count(*) from r where destino_rechazo = 'reproceso') as a_reproceso,

  -- Cuántos clientes y artículos distintos: un número alto repartido en
  -- pocos artículos es otro problema que el mismo número desparramado.
  (select count(distinct cliente_id) from r) as clientes,
  (select count(distinct articulo_id) from r) as articulos,

  -- El promedio por mes, para la decisión de "dos o veinte".
  -- `date - date` da DÍAS enteros en Postgres, no un intervalo: el
  -- `extract(epoch ...)` de la primera versión ni siquiera parseaba.
  (select round(count(*)::numeric / greatest(
       1::numeric, (max(fecha_operacion) - min(fecha_operacion))::numeric / 30.44), 1)
   from r) as por_mes;
