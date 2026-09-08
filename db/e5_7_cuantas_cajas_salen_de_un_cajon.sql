-- ¿Por que una caja armada puede costar UNA DOCEAVA parte del cajon?
-- Porque el BULTO CAMBIA DE TAMAÑO. costo_por_bulto_primera es
-- costo_total / bultos_primera, y NADA ata bultos_primera con
-- bultos_tomados: el unico check es bultos_primera >= 0. Un cajon grande
-- partido en 12 cajas chicas da 12 bultos de primera por 1 tomado, y el
-- costo por bulto cae 12 veces. No es un error: es el bulto que dejo de ser
-- el mismo objeto.
-- PREDICCION A VERIFICAR: x_hoy / x_conb (de e5_6b) tiene que dar parecido
-- a primera_por_tomado de aca. Si dan iguales, la causa es esta y no otra.
select (select fecha from corte_modelo where id=1) corte,
coalesce(a.nombre,'TOTAL') articulo,
count(*) guias,
round(coalesce(sum(rp.bultos_tomados),0),2) tomados,
round(coalesce(sum(rp.bultos_primera),0),2) primera,
round(coalesce(sum(rp.bultos_segunda),0),2) segunda,
round(coalesce(sum(rp.bultos_merma),0),2) merma,
round(sum(rp.bultos_primera)/nullif(sum(rp.bultos_tomados),0),2)
  primera_por_tomado
from reprocesos rp
join articulos a on a.id=rp.articulo_id,
(select fecha f0 from corte_modelo where id=1) c0
where rp.anulado_el is null and rp.tipo='normal'
and rp.fecha_operacion>c0.f0
group by grouping sets ((),(a.nombre))
order by grouping(a.nombre) desc,8 desc;
