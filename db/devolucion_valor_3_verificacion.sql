select 'devolucion_valor_2' as QUE_MIGRACION,
       count(*) filter (where m.compra_devolucion_id is not null) as atada,
       count(*) filter (where m.proveedor_devolucion_id is null) as sin_proveedor_suelto,
       max(m.compra_devolucion_id) as compra,
       max(cd.importe) as precio_compra,
       max(m.costo_por_bulto) as costo_armado,
       max(abs(m.cantidad) * cd.importe) as valor_nuevo,
       (select count(*) from movimientos_stock
         where destino_rechazo = 'devolucion_proveedor'
           and anulado_el is null) as poblacion_rechazos_al_proveedor
  from movimientos_stock m
  left join compras cd on cd.id = m.compra_devolucion_id
 where m.id = 170;

-- Verificacion de devolucion_valor_2, aparte del do. Esperado: atada 1 ·
-- sin_proveedor_suelto 1 · la compra elegida · su precio por cajon ·
-- valor_nuevo = 10 x ese precio.
