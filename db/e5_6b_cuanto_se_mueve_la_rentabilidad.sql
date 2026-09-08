-- BLOQUE B de 3. Corre DESPUES del A. Cuanto se mueve el costo atribuido a
-- los ARMADOS de los ultimos 30 dias si entra B (el armado toma caja armada
-- antes que cajon), por articulo y con el TOTAL arriba.
-- delta > 0 = con B el costo SUBE, o sea la rentabilidad ya reportada BAJA.
-- APROXIMA por lo bajo como e5_2/e5_4, y ademas cuesta los bultos que
-- cambian de pila con el costo PROMEDIO de cada lado, no lote por lote.
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
coalesce(sum(rest) filter (where trab),0) disp,
coalesce(sum(rest*cb) filter (where trab),0) pdisp from k group by aid,si),
x as (select aid,least(caj,disp) mal,
pl*least(caj,disp)/nullif(caj,0) hoy,
pdisp*least(caj,disp)/nullif(disp,0) conb from per)
select (select fecha from corte_modelo where id=1) corte,
coalesce(a.nombre,'TOTAL') articulo,
round(coalesce(sum(mal),0),2) bultos,
round(coalesce(sum(hoy),0),2) costo_hoy,
round(coalesce(sum(conb-hoy),0),2) delta
from x left join articulos a on a.id=x.aid
group by grouping sets ((),(a.nombre))
having grouping(a.nombre)=1 or coalesce(sum(mal),0)>0
order by grouping(a.nombre) desc,abs(coalesce(sum(conb-hoy),0)) desc;
