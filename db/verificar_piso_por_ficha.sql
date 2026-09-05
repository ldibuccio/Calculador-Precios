-- ¿ESTÁ ANDANDO EL PISO DE FECHA? Solo lectura, no escribe nada.
-- Calcula la cuenta POR FICHA de las dos formas —como estaba antes del
-- 04/09 y como queda con el piso— y las pone al lado. La columna 'cambio'
-- es exactamente lo que el piso sacó de esa ficha. Si todas las filas dan
-- cambio = 0, el piso no esta aplicando y hay que avisar.
with corte as (select fecha d from corte_modelo where id = 1),
vig as (
  select distinct on (cliente_id, fecha_operacion) id from pedidos
  where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
arm as (
  select articulo_id ai, ficha_id fi,
         sum(bultos_primera) t,
         sum(bultos_primera) filter (
           where fecha_operacion >= (select d from corte)) tp
  from reprocesos where anulado_el is null and ficha_id is not null group by 1,2),
sal as (
  select r.articulo_id ai, r.ficha_id fi,
         sum(coalesce(r.cantidad_armada, r.cantidad)) t,
         sum(coalesce(r.cantidad_armada, r.cantidad)) filter (
           where (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date
                 >= (select d from corte)) tp
  from pedidos_renglones r join vig v on v.id = r.pedido_id
  where r.armado_el is not null and r.anulado_el is null
    and r.articulo_id is not null and r.ficha_id is not null group by 1,2),
par as (select ai, fi from arm union select ai, fi from sal)
select a.nombre articulo,
       coalesce(nullif(btrim(fl.nombre_cliente),''), a.nombre) ficha,
       coalesce(arm.t,0)-coalesce(sal.t,0) antes_del_piso,
       coalesce(arm.tp,0)-coalesce(sal.tp,0) con_el_piso,
       (coalesce(arm.tp,0)-coalesce(sal.tp,0))
       - (coalesce(arm.t,0)-coalesce(sal.t,0)) cambio
from par
join articulos a on a.id = par.ai
join fichas_logistica fl on fl.id = par.fi
left join arm on arm.ai=par.ai and arm.fi=par.fi
left join sal on sal.ai=par.ai and sal.fi=par.fi
order by abs((coalesce(arm.tp,0)-coalesce(sal.tp,0))
             - (coalesce(arm.t,0)-coalesce(sal.t,0))) desc, 1;
