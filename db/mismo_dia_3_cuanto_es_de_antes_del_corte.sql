with c0 as (select fecha from corte_modelo where id = 1),
lotes as (
  select 'compra'::text as og, c.id as oid, coalesce(c.cantidad_cajones_real,0) as entrada
    from compras c where c.estado = 'recepcionado' and c.cantidad_cajones_real > 0
  union all
  select 'reproceso', r.id, r.bultos_primera from reprocesos r
   where r.anulado_el is null and r.bultos_primera > 0
  union all
  select m.tipo, m.id, m.cantidad from movimientos_stock m
   where m.anulado_el is null and m.cantidad > 0
),
atrib as (
  select rc.origen as og, rc.origen_id as oid, sum(rc.bultos) as todo,
         sum(rc.bultos) filter (where r.fecha_operacion > (select fecha from c0)) as post
    from reprocesos_consumos rc join reprocesos r on r.id = rc.reproceso_id
   where r.anulado_el is null and rc.origen <> 'sin_lote'
   group by rc.origen, rc.origen_id
),
cruce as (
  select a.og, a.oid, a.todo - l.entrada as exc,
         least(a.todo - l.entrada, coalesce(a.post,0)) as exc_post
    from atrib a join lotes l on l.og = a.og and l.oid = a.oid
)
select round(coalesce(sum(exc) filter (where exc > 0.001),0),2) as bultos_de_mas,
       round(coalesce(sum(exc_post) filter (where exc > 0.001),0),2) as de_mas_post_corte,
       round(coalesce(sum(exc-exc_post) filter (where exc > 0.001),0),2) as de_mas_pre_corte,
       count(*) filter (where exc > 0.001) as lotes_pasados,
       (select count(distinct rc.reproceso_id) from reprocesos_consumos rc
          join reprocesos r on r.id = rc.reproceso_id
          join cruce x on x.og = rc.origen and x.oid = rc.origen_id
         where r.anulado_el is null and x.exc > 0.001
           and r.fecha_operacion > (select fecha from c0)) as guias_tocadas_post,
       (select count(*) from reprocesos where anulado_el is null
         and tipo = 'normal' and fecha_operacion > (select fecha from c0)) as guias_post_corte,
       (select fecha from c0) as corte,
       (select max(fecha_operacion) from reprocesos
         where anulado_el is null) as ultima_guia_r
  from cruce;

-- Parte por el CORTE los 472 bultos de mismo_dia_1: lo de antes no lo rejuega
-- nadie; lo de despues es de estos dias. El reparto del exceso es una ELECCION:
-- va a las POSTERIORES primero, porque las de antes entraron cuando el lote
-- tenia con que. guias_tocadas_post es el TECHO del rebote, con su poblacion
-- al lado; ultima_guia_r, el testigo.

-- NO SE CORRIO, y la razon esta escrita para que no se lea como un olvido:
-- existia para dimensionar la URGENCIA DE RECOSTEAR los lotes sobre-atribuidos,
-- y el 16/09 el dueno decidio que esos 56 no se corrigen (etapa de prueba, los
-- costos todavia no cuentan). Sigue contestando lo que dice si algun dia la
-- plata de esos dias importa.
