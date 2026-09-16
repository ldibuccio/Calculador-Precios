with lotes as (
  select 'compra'::text as origen, c.id as origen_id,
         coalesce(c.cantidad_cajones_real, 0) as entrada
    from compras c
   where c.estado = 'recepcionado' and c.cantidad_cajones_real > 0
  union all
  select 'reproceso', r.id, r.bultos_primera
    from reprocesos r
   where r.anulado_el is null and r.bultos_primera > 0
  union all
  select m.tipo, m.id, m.cantidad
    from movimientos_stock m
   where m.anulado_el is null and m.cantidad > 0
),
atrib as (
  select rc.origen, rc.origen_id,
         sum(rc.bultos)                     as atribuido,
         count(distinct rc.reproceso_id)    as guias,
         sum(rc.bultos * coalesce(rc.costo_por_bulto, 0)) as plata
    from reprocesos_consumos rc
    join reprocesos r on r.id = rc.reproceso_id
   where r.anulado_el is null and rc.origen <> 'sin_lote'
   group by rc.origen, rc.origen_id
),
cruce as (
  select a.origen, a.origen_id, l.entrada, a.atribuido, a.guias,
         a.atribuido - l.entrada as exceso,
         case when l.entrada > 0 then a.plata / a.atribuido * (a.atribuido - l.entrada) end as plata_del_exceso
    from atrib a
    join lotes l on l.origen = a.origen and l.origen_id = a.origen_id
)
select count(*) filter (where exceso > 0.001)                as lotes_pasados,
       count(*)                                              as lotes_consumidos,
       round(coalesce(sum(exceso) filter (where exceso > 0.001), 0), 2) as bultos_de_mas,
       round(coalesce(max(exceso) filter (where exceso > 0.001), 0), 2) as peor_lote,
       round(coalesce(sum(plata_del_exceso) filter (where exceso > 0.001), 0), 2) as plata_de_mas,
       (select count(*) from reprocesos where anulado_el is null and tipo = 'normal') as guias_normales,
       (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r
  from cruce;

-- ---------------------------------------------------------------------------
-- CUANTO se tomo de mas de un lote, segun lo ESCRITO en reprocesos_consumos
-- (documento congelado: es el costo que quedo). `exceso` es lo que se
-- atribuyo a un lote por encima de lo que ese lote tenia.
-- `lotes_consumidos` es la poblacion: `lotes_pasados 2 de 300` se lee solo.
-- `plata_de_mas` prorratea el costo escrito, asi que es el costo que se
-- imputo a bultos que ese lote no tenia — no una perdida.
-- Un cero aca NO dice que este todo bien: dice que lo escrito cierra. El
-- rejuego del stock puede decir otra cosa, y de hecho la dice.
