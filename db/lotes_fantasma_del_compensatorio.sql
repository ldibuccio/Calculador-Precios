-- ############################################################################
-- LOS LOTES FANTASMA DEL COMPENSATORIO. Solo lectura, no escriben nada.
--
-- Un compensatorio POSITIVO —el de un artículo que estaba en negativo— entra
-- al FIFO COMO UN LOTE, porque las entradas del reparto son "movimientos_stock
-- con cantidad > 0" sin mirar el tipo. Es mercadería que no existe.
--
-- Los compensatorios NEGATIVOS no tienen el problema: entran como salida, que
-- es lo correcto, y consumen lotes viejos.
-- ############################################################################

-- ===========================================================================
-- LOS LOTES FANTASMA DEL COMPENSATORIO. Solo lectura, no escribe nada.
-- Un compensatorio POSITIVO (el de un artículo que estaba en negativo) entra
-- al FIFO como un LOTE, porque las entradas son "movimientos_stock con
-- cantidad > 0" sin mirar el tipo. Es mercadería que no existe, y encima sin
-- costo: el CHECK de la base PROHÍBE que cierre_modelo_viejo tenga
-- costo_por_bulto.
-- Los negativos NO son lotes: entran como salida, que es lo correcto.
select m.fecha_operacion corte_menos_uno,
       count(*) filter (where m.cantidad > 0) lotes_fantasma,
       coalesce(sum(m.cantidad) filter (where m.cantidad > 0), 0) bultos_fantasma,
       count(*) filter (where m.cantidad < 0) compensatorios_negativos,
       count(*) total_articulos_compensados
from movimientos_stock m
where m.anulado_el is null and m.tipo = 'cierre_modelo_viejo'
group by 1
order by 1;

-- ===========================================================================
-- EL DETALLE: qué artículos tienen lote fantasma y de qué tamaño.
-- 'costo' sale NULL siempre y no es un olvido: el CHECK
-- movimientos_stock_vinculo_solo_reingreso prohíbe que este tipo lo tenga.
select m.fecha_operacion corte_menos_uno, a.nombre articulo,
       m.cantidad bultos_del_lote, m.stock_sistema estaba_en,
       m.costo_por_bulto costo
from movimientos_stock m
join articulos a on a.id = m.articulo_id
where m.anulado_el is null and m.tipo = 'cierre_modelo_viejo' and m.cantidad > 0
order by m.fecha_operacion desc, m.cantidad desc;
