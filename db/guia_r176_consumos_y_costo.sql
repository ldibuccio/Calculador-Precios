-- QUÉ CONSUMIÓ LA GUÍA R176 y de qué lote salió cada bulto. Los consumos son
-- un documento CONGELADO: esto es lo que se escribió al cargarla.
-- La columna QUE_MUESTRA_LA_PANTALLA reproduce el if/elif de
-- deposito_stock_guias_r.html: si dice "Sin lote" para un origen que SÍ es un
-- lote real, el problema es del cartel y no de la guía.
select r.id as guia, r.fecha_operacion, a.nombre as articulo,
       r.bultos_tomados, r.bultos_primera, r.bultos_segunda, r.bultos_merma,
       r.costo_total, r.costo_por_bulto_primera, r.consumos_editados,
       c.origen, c.origen_id, c.compra_id, c.bultos, c.costo_por_bulto,
       case c.origen
         when 'compra' then 'De la guía ... proveedor'
         when 'ajuste' then 'De un ajuste (ej. stock inicial)'
         when 'reingreso_rechazo' then 'De un reingreso por rechazo'
         when 'reproceso' then 'De la guía R' || c.origen_id
         when 'cierre_modelo_viejo' then 'Del cierre del modelo viejo'
         else 'Sin lote (se tomó más de lo que había en el sistema)'
       end as que_muestra_la_pantalla,
       (c.origen not in ('compra','ajuste','reingreso_rechazo','reproceso',
                         'cierre_modelo_viejo','sin_lote')) as el_cartel_miente,
       -- De dónde salió el costo, según el origen del lote
       case c.origen
         when 'compra' then (select 'compra ' || cp.id || ' importe ' || cp.importe
                               from compras cp where cp.id = c.compra_id)
         when 'reproceso' then (select 'guía R' || rp.id || ' costo/caja ' || rp.costo_por_bulto_primera
                                  from reprocesos rp where rp.id = c.origen_id)
         else (select 'movimiento ' || m.id || ' tipo ' || m.tipo || ' costo/bulto '
                      || coalesce(m.costo_por_bulto::text,'(sin costo)') || ' — ' || m.motivo
                 from movimientos_stock m where m.id = c.origen_id)
       end as de_donde_salio_el_costo
from reprocesos r
join articulos a on a.id = r.articulo_id
left join reprocesos_consumos c on c.reproceso_id = r.id
where r.id = 176
order by c.id;
