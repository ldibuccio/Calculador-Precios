with v as (select current_date - 90 as desde),
pob as (
  select count(*)                                              as guias_en_la_ventana,
         count(*) filter (where x.lleva_caja_nuestra is null)  as sin_declarar,
         (select max(y.fecha_operacion) from reprocesos y
           where y.anulado_el is null)                         as ultima_guia_r
    from reprocesos x, v
   where x.anulado_el is null and x.tipo = 'normal'
     and x.fecha_operacion >= v.desde
),
costo as (
  select distinct on (h.envase_id) h.envase_id, h.costo
    from envases_costo_historial h
   where h.vigente_desde <= current_date
   order by h.envase_id, h.vigente_desde desc
)
select e.nombre                                               as envase,
       coalesce(sum(r.bultos_primera), 0)                     as por_primera,
       coalesce(sum(r.bultos_segunda), 0)                     as por_segunda,
       round(100 * coalesce(sum(r.bultos_segunda), 0)
             / nullif(sum(r.bultos_primera + r.bultos_segunda), 0), 1)
                                                              as pct_sin_primera,
       count(r.id)                                            as guias,
       c.costo                                                as costo_caja,
       round(c.costo * coalesce(sum(r.bultos_segunda), 0), 2) as pesos_sin_cobrar,
       v.desde, p.guias_en_la_ventana, p.sin_declarar, p.ultima_guia_r
  from envases e
  cross join v
  cross join pob p
  left join reprocesos r
         on r.envase_id = e.id
        and r.anulado_el is null
        and r.tipo = 'normal'
        and r.lleva_caja_nuestra is true
        and r.fecha_operacion >= v.desde
  left join costo c on c.envase_id = e.id
 where e.activo = true
 group by e.nombre, c.costo, v.desde,
          p.guias_en_la_ventana, p.sin_declarar, p.ultima_guia_r
 order by 7 desc nulls last, 1;

-- ---------------------------------------------------------------------------
-- El envase se cobra POR UNIDAD DE PRIMERA VENDIDA; la segunda sale en caja
-- nuestra sin una primera atras, asi que la primera la subsidia.
-- `pct_sin_primera` es por cuanto esta corta la tasa que YA existe.
-- `sin_declarar` es EL HUECO y `guias_en_la_ventana` su poblacion; `guias 0`
-- puede ser un envase sin usar; `ultima_guia_r` dice si la base vota. Las dos
-- columnas se escriben desde el 16/09: hoy mide una semana, no 90 dias.
-- Todo lo demas, en docs/el_costo_de_las_cajas_que_salen_sin_venta.md
