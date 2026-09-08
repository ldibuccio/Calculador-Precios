-- BLOQUE B de 3. Corre DESPUES del A. Cuanto se mueve el costo atribuido a
-- los ARMADOS de los ultimos 30 dias si entra B (el armado toma caja armada
-- antes que cajon), por articulo y con el TOTAL arriba.
-- delta > 0 = con B el costo SUBE, o sea la rentabilidad ya reportada BAJA.
-- APROXIMA por lo bajo como e5_2/e5_4, y ademas cuesta los bultos que
-- cambian de pila con el costo PROMEDIO de cada lado, no lote por lote.
-- caja_s_costo / cajon_s_costo: bultos cuyo lote NO tiene costo. Un lote sin
-- costo suma bultos y no suma pesos, asi que ESE lado sale barato de mentira.
-- Con caja_s_costo > 0 el delta esta sesgado a NEGATIVO y no se puede usar.
-- x_hoy y x_conb son los pesos por bulto de cada lado: si dan iguales, el
-- delta 0 es real (una guia R sin merma ni segunda pasa el costo derecho).
with p as (select aid,d,cb,trab,lado,sum(q) over w-q ini,sum(q) over w fin
from e5_mov window w as (partition by aid,(lado=1) order by d,m)),
j as (select s.aid,s.ini si,s.fin sf,l.trab,l.cb,l.ini li,l.fin lf
from p s join p l on l.aid=s.aid and l.lado=1 and l.d<=s.d
where s.lado=3 and s.d>=(now() at time zone
'America/Argentina/Buenos_Aires')::date-30),
k as (select aid,si,trab,cb,greatest(least(sf,lf)-greatest(si,li),0) ov,
greatest(lf-greatest(li,sf),0) rest from j),
per as (select aid,coalesce(sum(ov) filter (where not trab),0) caj,
coalesce(sum(ov*cb) filter (where not trab),0) pl,
coalesce(sum(ov) filter (where not trab and cb is null),0) sc,
coalesce(sum(rest) filter (where trab),0) disp,
coalesce(sum(rest*cb) filter (where trab),0) pdisp,
coalesce(sum(rest) filter (where trab and cb is null),0) sct
from k group by aid,si),
x as (select aid,least(caj,disp) mal,caj,pl,sc,disp,pdisp,sct,
pl*least(caj,disp)/nullif(caj,0) hoy,
pdisp*least(caj,disp)/nullif(disp,0) conb from per)
select (select fecha from corte_modelo where id=1) corte,
coalesce(a.nombre,'TOTAL') articulo,
round(coalesce(sum(mal),0),2) bultos,
round(coalesce(sum(hoy),0),2) costo_hoy,
round(coalesce(sum(conb-hoy),0),2) delta,
round(sum(pl)/nullif(sum(caj),0),2) x_hoy,
round(sum(pdisp)/nullif(sum(disp),0),2) x_conb,
round(coalesce(sum(sct),0),2) caja_s_costo,
round(coalesce(sum(sc),0),2) cajon_s_costo
from x left join articulos a on a.id=x.aid
group by grouping sets ((),(a.nombre))
having grouping(a.nombre)=1 or coalesce(sum(mal),0)>0
order by grouping(a.nombre) desc,abs(coalesce(sum(conb-hoy),0)) desc;
