select 'devolucion_valor_1' as QUE_CONSULTA,
       count(*) over () as poblacion,
       m.id, m.fecha_operacion as fecha,
       case when m.tipo = 'devolucion_deposito' then 'deposito' else 'rechazo' end as camino,
       a.nombre as articulo, coalesce(pc.nombre, ps.nombre) as proveedor,
       m.compra_devolucion_id as compra, abs(m.cantidad) as bultos,
       case when fd.envase_id is not null then 'caja de Dia'
            when m.tipo = 'devolucion_deposito' then 'deposito'
            else 'cajon' end as en_que,
       m.costo_por_bulto as costo_armado, cd.importe as precio_compra,
       abs(m.cantidad) * case
         when m.tipo = 'devolucion_deposito' then cd.importe
         else coalesce(case when m.compra_devolucion_id is not null
                             and fd.envase_id is null then cd.importe end,
                       m.costo_por_bulto) end as valor_hoy,
       abs(m.cantidad) * case
         when m.tipo = 'devolucion_deposito'
           or (m.compra_devolucion_id is not null and fd.envase_id is null)
         then cd.importe else m.costo_por_bulto end as valor_nuevo
  from movimientos_stock m
  join articulos a on a.id = m.articulo_id
  left join compras cd on cd.id = m.compra_devolucion_id
  left join proveedores pc on pc.id = cd.proveedor_id
  left join proveedores ps on ps.id = m.proveedor_devolucion_id
  left join pedidos_renglones r on r.id = m.pedido_renglon_id
  left join fichas_logistica fd on fd.id = r.ficha_id
 where m.anulado_el is null
   and (m.tipo = 'devolucion_deposito'
        or m.destino_rechazo = 'devolucion_proveedor')
 order by m.fecha_operacion, m.id;

-- devolucion_valor_1: TODAS las devoluciones al proveedor no anuladas, por
-- los dos caminos, con lo que valen HOY (v1061) y lo que valen con la regla
-- de Lionel (01/10). Solo lee.
--   costo_armado   el costo congelado del rechazo (FIFO del armado, por kilo)
--   precio_compra  compras.importe de la compra atada (por cajón)
--   valor_hoy      lo que muestran hoy Movimientos, la planilla y la Rentab.
--   valor_nuevo    lo que van a mostrar: el precio de la compra; en caja de
--                  Día o sin compra, el costo congelado (sin cambio).
-- valor_hoy <> valor_nuevo solo en rechazos con compra SIN PRECIO (hoy caen
-- al costo del armado, despues dicen "sin precio").
