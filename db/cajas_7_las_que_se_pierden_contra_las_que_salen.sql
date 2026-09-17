with v as (select current_date - 90 as desde),
perdidas as (
  select f.id as ficha_id, sum(m.cantidad) as cajas from movimientos_stock m
    join pedidos_renglones pr on pr.id = m.pedido_renglon_id
    join fichas_logistica f on f.id = pr.ficha_id, v
   where m.anulado_el is null and m.tipo = 'reingreso_rechazo'
     and m.destino_rechazo in ('segunda', 'devolucion_proveedor')
     and f.envase_id is not null and m.fecha_operacion >= v.desde
   group by f.id
),
salieron as (
  select r.ficha_id,
         sum(r.bultos_primera) filter (where r.lleva_caja_nuestra is true) as cajas,
         count(*) filter (where r.lleva_caja_nuestra is null) as sin_declarar
    from reprocesos r cross join v
   where r.anulado_el is null and r.tipo = 'normal' and r.ficha_id is not null
     and r.fecha_operacion >= v.desde group by r.ficha_id
),
costo as (
  select distinct on (h.envase_id) h.envase_id, h.costo from envases_costo_historial h
   where h.vigente_desde <= current_date order by h.envase_id, h.vigente_desde desc
)
select cl.nombre as cliente, a.nombre as articulo,
       coalesce(p.cajas,0) as perdidas, coalesce(s.cajas,0) as salieron,
       round(100*coalesce(p.cajas,0)/nullif(s.cajas,0),1) as pct,
       coalesce(s.sin_declarar,0) as sin_declarar,
       round(c.costo*coalesce(p.cajas,0),2) as pesos, v.desde,
       (select count(*) from fichas_logistica where envase_id is not null) as poblacion,
       (select max(fecha_operacion) from reprocesos where anulado_el is null) as ult_guia
  from fichas_logistica f cross join v
  join clientes cl on cl.id = f.cliente_id
  join articulos a on a.id = f.articulo_id
  left join perdidas p on p.ficha_id = f.id
  left join salieron s on s.ficha_id = f.id
  left join costo c on c.envase_id = f.envase_id
 where coalesce(p.cajas, 0) > 0 or coalesce(s.cajas, 0) > 0
 order by pesos desc nulls last;

-- `pct`: PERDIDAS sobre las que SALIERON. Un numero solo no se lee: 149
-- sobre 5.000 es 3% y sobre 800 es 19%.
-- `sin_declarar` HACE LEGIBLE UN `pct` EN NULL: `salieron` cuenta solo las
-- guias con la caja DECLARADA y `perdidas` la DERIVA de la ficha. Una de
-- envase VARIABLE (mango, cherry) queda NULL si nadie contesto: ahi el
-- `pct` no se lee y `perdidas` es un TECHO.
--
-- PERDIDAS: `segunda` y `devolucion_proveedor`. `reproceso` tambien la
-- pierde (se tira, 17/09) y no esta porque ya se cobra en
-- `rechazos_perdidos`. `stock` la reusa.
--
-- `poblacion`: contra cuanto se cuenta. `ult_guia`: si la base vota.
