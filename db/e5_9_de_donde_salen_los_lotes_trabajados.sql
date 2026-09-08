-- DE DONDE SALE CADA LOTE TRABAJADO. e5_7 mira solo guias R tipo='normal',
-- y e5_6b cuenta como trabajado TRES fuentes distintas. Por eso Pomelo no
-- aparece en e5_7 y si tiene pila trabajada, y por eso comparar el ratio de
-- e5_7 contra el x_conb de e5_6b es comparar poblaciones distintas.
--  - normal:   guia R de todos los dias. Es la unica con tomados > 0, o sea
--              la unica que tiene ratio primera/tomados.
--  - inicial:  la foto del corte. PRODUCE SIN CONSUMIR (tomados = 0) y su
--              costo se cargo A MANO: no sale de ningun cajon.
--  - reingreso: volvio del cliente. Nace en movimientos_stock, sin reproceso.
-- Si x_inicial o x_reing son mucho mas bajos que x_normal, esos lotes tiran
-- el x_conb para abajo y el ratio contra e5_7 nunca iba a cerrar.
with c0 as (select fecha f0 from corte_modelo where id=1),
l(aid,fuente,b,pl) as (
 select rp.articulo_id,rp.tipo,rp.bultos_primera,
  rp.bultos_primera*rp.costo_por_bulto_primera
 from reprocesos rp,c0 where rp.anulado_el is null and rp.bultos_primera>0
 and ((rp.tipo='inicial' and rp.fecha_operacion=c0.f0)
      or rp.fecha_operacion>c0.f0)
 union all
 select m.articulo_id,'reingreso',m.cantidad,m.cantidad*m.costo_por_bulto
 from movimientos_stock m,c0 where m.anulado_el is null
 and m.tipo='reingreso_rechazo' and m.cantidad>0
 and (m.destino_rechazo is null or m.destino_rechazo='stock')
 and m.fecha_operacion>c0.f0)
select (select f0 from c0) corte,coalesce(a.nombre,'TOTAL') articulo,
round(coalesce(sum(b) filter (where fuente='normal'),0),2) b_normal,
round(sum(pl) filter (where fuente='normal')
 /nullif(sum(b) filter (where fuente='normal'),0),2) x_normal,
round(coalesce(sum(b) filter (where fuente='inicial'),0),2) b_inicial,
round(sum(pl) filter (where fuente='inicial')
 /nullif(sum(b) filter (where fuente='inicial'),0),2) x_inicial,
round(coalesce(sum(b) filter (where fuente='reingreso'),0),2) b_reing,
round(sum(pl) filter (where fuente='reingreso')
 /nullif(sum(b) filter (where fuente='reingreso'),0),2) x_reing
from l join articulos a on a.id=l.aid
group by grouping sets ((),(a.nombre))
order by grouping(a.nombre) desc,3 desc;
