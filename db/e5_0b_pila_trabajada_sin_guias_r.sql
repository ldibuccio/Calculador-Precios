-- ¿Puede haber pila TRABAJADA sin una sola guia R? Si: TIPOS_LOTE_TRABAJADO
-- es ("reproceso", "reingreso_rechazo"), y el reingreso por rechazo nace en
-- movimientos_stock, no en reprocesos. Salio armado y volvio.
-- Solo cuenta como LOTE el que vuelve al stock normal: destino segunda o
-- reproceso sale del circuito (su costo ya se imputo como perdida).
-- Correr en LAS DOS. Con guias_r y reingresos_lote en cero, E5 no existe
-- en esa base y A y B corren sin nada que hacer.
select (select fecha from corte_modelo where id=1) corte,
(select count(*) from reprocesos where anulado_el is null
 and bultos_primera>0) guias_r_con_cajas,
(select count(*) from movimientos_stock m
 where m.anulado_el is null and m.tipo='reingreso_rechazo'
 and (m.destino_rechazo is null or m.destino_rechazo='stock')
 and m.fecha_operacion>(select fecha from corte_modelo where id=1)
) reingresos_lote,
(select coalesce(sum(m.cantidad),0) from movimientos_stock m
 where m.anulado_el is null and m.tipo='reingreso_rechazo'
 and (m.destino_rechazo is null or m.destino_rechazo='stock')
 and m.fecha_operacion>(select fecha from corte_modelo where id=1)
) reingresos_bultos,
(select count(*) from movimientos_stock m
 where m.anulado_el is null and m.tipo='reingreso_rechazo'
 and m.destino_rechazo in ('segunda','reproceso')
 and m.fecha_operacion>(select fecha from corte_modelo where id=1)
) reingresos_fuera_del_stock,
(select count(*) from movimientos_stock
 where anulado_el is null and tipo='reingreso_rechazo') reingresos_historicos,
(select max(fecha_operacion) from movimientos_stock
 where anulado_el is null and tipo='reingreso_rechazo') ultimo_reingreso;
