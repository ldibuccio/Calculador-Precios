-- ¿QUÉ HAY EN EL POOL DE SEGUNDA, Y DE CUÁNDO? Solo lectura.
-- El pool de segunda es la ÚNICA cuenta que ningún corte rebasea: el
-- compensatorio es un movimiento de stock y esta cuenta no lee movimientos.
-- Así que la segunda anterior al corte SIGUE contando, y si además se carga
-- la contada esta noche, el pool queda sumando las dos.
with corte as (select fecha d from corte_modelo where id = 1),
prod as (
  select articulo_id ai,
         sum(bultos_segunda) filter (where fecha_operacion < (select d from corte)) antes,
         sum(bultos_segunda) filter (where fecha_operacion >= (select d from corte)) desde
  from reprocesos where anulado_el is null and bultos_segunda > 0 group by 1),
rech as (
  select articulo_id ai, sum(bultos_segunda) t from movimientos_stock
  where anulado_el is null and destino_rechazo in ('segunda','reproceso') group by 1),
rem as (
  select articulo_id ai, sum(bultos) t from remitos_segunda
  where anulado_el is null group by 1)
select a.nombre articulo,
       coalesce(prod.antes,0) segunda_antes_del_corte,
       coalesce(prod.desde,0) segunda_desde_el_corte,
       coalesce(rech.t,0) de_rechazos,
       coalesce(rem.t,0) ya_remitida,
       coalesce(prod.antes,0)+coalesce(prod.desde,0)+coalesce(rech.t,0)-coalesce(rem.t,0) pool_hoy
from articulos a
left join prod on prod.ai = a.id
left join rech on rech.ai = a.id
left join rem on rem.ai = a.id
where coalesce(prod.antes,0)+coalesce(prod.desde,0)+coalesce(rech.t,0)-coalesce(rem.t,0) <> 0
   or coalesce(prod.antes,0) <> 0
order by 2 desc, 1;
