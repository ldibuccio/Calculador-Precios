-- POR QUE e5_7 NO ALCANZO. Mi prediccion (x_hoy/x_conb = primera/tomados)
-- suponia sin decirlo que la caja disponible salio DEL MISMO cajon que el
-- armado se esta comiendo. No es asi. La identidad completa es:
--   costo_por_bulto_primera = cb_consumido * (tomados / primera)
-- y entonces
--   x_hoy / x_conb = (cb_armado / cb_consumido) * (primera / tomados)
-- El primer factor es el que falta: el cajon que la guia R se comio NO es
-- el que come el armado. Y no es ruido: la guia R va ANTES en el orden del
-- FIFO, asi que se lleva el lote mas viejo y al armado le queda el nuevo.
-- x_consumido es lo que las guias R pagaron por lo que tomaron; comparalo
-- contra el x_hoy de e5_6b. teorico vs real verifica la identidad de arriba.
with c0 as (select fecha f0 from corte_modelo where id=1),
g as (select rp.id gid,rp.articulo_id aid,rp.bultos_tomados t,
rp.bultos_primera p,rp.costo_por_bulto_primera cbp
from reprocesos rp,c0 where rp.anulado_el is null and rp.tipo='normal'
and rp.fecha_operacion>c0.f0),
tot as (select aid,sum(t) t,sum(p) p,sum(p*cbp) pcbp,
sum(p) filter (where cbp is null) p_sin_costo from g group by aid),
con as (select g.aid,sum(rc.bultos) b,sum(rc.bultos*rc.costo_por_bulto) pl,
sum(rc.bultos) filter (where rc.costo_por_bulto is null) b_sin_costo
from g join reprocesos_consumos rc on rc.reproceso_id=g.gid group by g.aid)
select (select f0 from c0) corte,coalesce(a.nombre,'TOTAL') articulo,
round(sum(c.pl)/nullif(sum(c.b),0),2) x_consumido,
round(sum(t.p)/nullif(sum(t.t),0),2) p_por_t,
round((sum(c.pl)/nullif(sum(c.b),0))
 /nullif(sum(t.p)/nullif(sum(t.t),0),0),2) x_prim_teorico,
round(sum(t.pcbp)/nullif(sum(t.p),0),2) x_prim_real,
round(coalesce(sum(c.b_sin_costo),0),2) tomado_s_costo,
round(coalesce(sum(t.p_sin_costo),0),2) primera_s_costo
from tot t join con c on c.aid=t.aid
join articulos a on a.id=t.aid
group by grouping sets ((),(a.nombre))
order by grouping(a.nombre) desc,3 desc;
