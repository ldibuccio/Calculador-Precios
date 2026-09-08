-- CORRER PRIMERO, EN LAS DOS BASES, Y COMPARAR. Todas las consultas de E5
-- leen `corte_modelo where id=1`. Si esa fila no existe, el CTE del corte
-- sale vacio, el cross join deja todo en cero y e5_3/e5_4 devuelven una fila
-- de ceros que se lee igual que "aca no hay problema".
-- Esto dice contra QUE se esta midiendo antes de medir. Sin FROM a proposito:
-- asi la fila vuelve siempre, aunque no haya corte cargado (corte = NULL).
select (select count(*) from corte_modelo) filas_corte,
(select fecha from corte_modelo where id=1) corte,
(select count(*) from reprocesos rp where rp.anulado_el is null
 and rp.tipo='normal' and rp.fecha_operacion>
 (select fecha from corte_modelo where id=1)) guias_r_post_corte,
(select count(*) from reprocesos rp where rp.anulado_el is null
 and rp.tipo='normal' and rp.fecha_operacion=
 (select fecha from corte_modelo where id=1)) guias_r_EL_dia_del_corte,
(select count(*) from reprocesos rp where rp.anulado_el is null
 and rp.tipo='inicial') guias_r_inicial,
(select count(*) from compras c where c.estado='recepcionado'
 and (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date>
 (select fecha from corte_modelo where id=1)) compras_post_corte,
(select count(*) from pedidos_renglones r where r.armado_el is not null
 and r.anulado_el is null and (r.armado_el at time zone
 'America/Argentina/Buenos_Aires')::date>
 (select fecha from corte_modelo where id=1)) armados_post_corte,
(select max(fecha_operacion) from reprocesos
 where anulado_el is null) ultima_guia_r;
