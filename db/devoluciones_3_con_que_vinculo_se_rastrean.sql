-- ¿Cuantas devoluciones al proveedor hay, y con que se las puede rastrear?
--
-- Va de 3 y no de 1: `devoluciones_2_cuantas_veces.sql` ya existia y mide
-- OTRA cosa —el rechazo que volvia ANTES de que el cuarto destino
-- existiera—. Dos archivos numerados al reves de como pasaron se cobran en
-- la proxima lectura, cuando ya nadie se acuerda de cual vino primero.
--
-- LA PREGUNTA QUE DECIDE: para reclamarle al proveedor hace falta decir "de
-- la compra del martes te devolvi 8 bultos". El movimiento NO guarda la
-- compra: guarda `pedido_renglon_id` (de que renglon armado volvio) y
-- `proveedor_devolucion_id` (el proveedor ELEGIDO DE UNA LISTA). La compra
-- solo se alcanza rejugando el FIFO desde el renglon, y eso solo existe si
-- el reingreso esta VINCULADO a un renglon.
--
-- Por eso las columnas van de a pares: cuantas devoluciones hay y cuantas
-- de esas tienen cada pieza de la cadena. `sin_renglon` es el caso sin
-- salida: de esas no hay forma de llegar a la compra ni construyendo nada.
--
-- `reingresos` es la POBLACION y decide si vale construir algo. Y los
-- TESTIGOS al lado: sobre una base quieta estos ceros no significan nada.
select
    count(*) filter (where tipo = 'reingreso_rechazo')                     as reingresos,
    count(*) filter (where destino_rechazo = 'devolucion_proveedor')       as devoluciones,
    count(*) filter (where destino_rechazo = 'devolucion_proveedor'
                       and proveedor_devolucion_id is not null)            as con_proveedor,
    count(*) filter (where destino_rechazo = 'devolucion_proveedor'
                       and pedido_renglon_id is not null)                  as con_renglon,
    count(*) filter (where destino_rechazo = 'devolucion_proveedor'
                       and pedido_renglon_id is null)                      as sin_renglon,
    count(distinct proveedor_devolucion_id)
      filter (where destino_rechazo = 'devolucion_proveedor')              as proveedores_distintos,
    coalesce(sum(cantidad) filter (where destino_rechazo = 'devolucion_proveedor'), 0)
                                                                           as bultos_devueltos,
    min(fecha_operacion) filter (where destino_rechazo = 'devolucion_proveedor')
                                                                           as primera_devolucion,
    max(fecha_operacion) filter (where destino_rechazo = 'devolucion_proveedor')
                                                                           as ultima_devolucion,
    max(fecha_operacion) filter (where tipo = 'reingreso_rechazo')         as ultimo_reingreso
from movimientos_stock
where anulado_el is null
  and fecha_operacion >= current_date - 90;
