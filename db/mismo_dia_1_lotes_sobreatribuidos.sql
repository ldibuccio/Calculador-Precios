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
         sum(rc.bultos)                                    as atribuido,
         sum(rc.bultos * coalesce(rc.costo_por_bulto, 0))  as plata
    from reprocesos_consumos rc
    join reprocesos r on r.id = rc.reproceso_id
   where r.anulado_el is null and rc.origen <> 'sin_lote'
   group by rc.origen, rc.origen_id
),
cruce as (
  select a.atribuido, l.entrada, a.atribuido - l.entrada as exceso,
         a.plata / nullif(a.atribuido, 0) * (a.atribuido - l.entrada) as plata_del_exceso
    from atrib a
    left join lotes l on l.origen = a.origen and l.origen_id = a.origen_id
)
select count(*) filter (where exceso > 0.001)                        as lotes_pasados,
       count(*) filter (where entrada is not null)                   as lotes_consumidos,
       round(coalesce(sum(exceso) filter (where exceso > 0.001), 0), 2)     as bultos_de_mas,
       round(coalesce(max(exceso) filter (where exceso > 0.001), 0), 2)     as peor_lote,
       round(coalesce(sum(plata_del_exceso) filter (where exceso > 0.001), 0), 2) as plata_de_mas,
       count(*) filter (where entrada is null)                       as lote_no_hallado,
       (select count(*) from reprocesos where anulado_el is null and tipo = 'normal') as guias_normales,
       (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r
  from cruce;

-- ---------------------------------------------------------------------------
-- Cuanto se tomo de mas de un lote segun lo ESCRITO en reprocesos_consumos
-- (congelado: es el costo que quedo). `plata_de_mas` prorratea ese costo, o
-- sea lo imputado a bultos que el lote no tenia.
--
-- `lote_no_hallado` es EL HUECO, y por eso el join es LEFT: con uno interno un
-- consumo cuyo lote hoy no existe se caia EN SILENCIO y esto daba "todo bien".
-- Si no da 0, `lotes_pasados` cuenta de menos.
--
-- Y un cero NO dice que este bien: dice que lo ESCRITO cierra. El rejuego del
-- stock puede decir otra cosa, y sobre este bug la dice.

-- CONTESTADA el 16/09 (Frutamax): lotes_pasados 56 · lotes_consumidos 281 ·
-- bultos_de_mas 472 · peor_lote 31 · plata_de_mas $13.841.434 ·
-- lote_no_hallado 0. Palmala no vota (base parada).
--
-- Y esos $13,8M son la EXPOSICION, no el error: los 472 bultos existieron y
-- se costearon al precio del lote al que quedaron mal pegados. El error de
-- cada guia es la DIFERENCIA contra el lote del que salieron en serio.
--
-- EL AGUJERO ESTA CERRADO desde el 16/09 (el freno cuenta el mismo dia), asi
-- que este numero YA NO PUEDE CRECER: correrla de nuevo devuelve lo mismo por
-- construccion. Y los 56 que quedaron NO SE CORRIGEN — son de la etapa de
-- prueba, decidido por el dueno el 16/09. Ver CLAUDE.md, corolario 73.
