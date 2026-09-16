with v as (select current_date - 90 as desde),
perdidas as (
  select f.id as ficha_id, sum(m.cantidad) as cajas from movimientos_stock m
    join pedidos_renglones pr on pr.id = m.pedido_renglon_id
    join fichas_logistica f   on f.id = pr.ficha_id
    cross join v
   where m.anulado_el is null and m.tipo = 'reingreso_rechazo'
     and m.destino_rechazo in ('segunda', 'devolucion_proveedor')
     and f.envase_id is not null and m.fecha_operacion >= v.desde
   group by f.id
),
salieron as (
  select r.ficha_id, sum(r.bultos_primera) as cajas
    from reprocesos r cross join v
   where r.anulado_el is null and r.tipo = 'normal'
     and r.lleva_caja_nuestra is true and r.ficha_id is not null
     and r.fecha_operacion >= v.desde
   group by r.ficha_id
),
costo as (
  select distinct on (h.envase_id) h.envase_id, h.costo
    from envases_costo_historial h where h.vigente_desde <= current_date
   order by h.envase_id, h.vigente_desde desc
)
select cl.nombre as cliente, a.nombre as articulo,
       coalesce(p.cajas,0) as perdidas, coalesce(s.cajas,0) as salieron,
       round(100*coalesce(p.cajas,0)/nullif(s.cajas,0),1) as pct,
       c.costo as costo_caja,
       round(c.costo*coalesce(p.cajas,0),2) as pesos, v.desde,
       (select count(*) from fichas_logistica where envase_id is not null) as fichas_con_envase,
       (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r
  from fichas_logistica f cross join v
  join clientes cl on cl.id = f.cliente_id
  join articulos a on a.id = f.articulo_id
  left join perdidas p on p.ficha_id = f.id
  left join salieron s on s.ficha_id = f.id
  left join costo    c on c.envase_id = f.envase_id
 where coalesce(p.cajas, 0) > 0 or coalesce(s.cajas, 0) > 0
 order by pct desc nulls last, perdidas desc;

-- `pct` ES EL FACTOR: cajas que se PIERDEN sobre las que SALEN, por ficha.
-- Un numero solo no se lee: 149 sobre 5.000 es 3% y sobre 800 es 19%.
--
-- PERDIDAS: el RECHAZO que se va de nuevo — `segunda` (al Puesto) y
-- `devolucion_proveedor`. No entran `reproceso` (esa caja se libera y ya la
-- suma `liberadas`) ni `stock` (neutra). Ni la segunda de un REPROCESO:
-- queda en el cajon del proveedor y nunca fue caja nuestra (16/09).
--
-- EL ENVASE SALE DE LA FICHA DE HOY: las dos puertas no lo declaran, asi que
-- cambiarle el envase re-etiqueta esto en silencio. El porque y que hacer con
-- el numero, en docs/el_costo_de_las_cajas_*.md
--
-- `fichas_con_envase` es la poblacion; `ultima_guia_r`, si la base vota.
