with recibidas as (
  select c.articulo_id,
         coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon) as contenido
    from compras c
   where c.estado = 'recepcionado'
     and c.procesada_el >= current_date - 90
     and coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon) > 0
),
valores as (
  select articulo_id, contenido, count(*) as veces
    from recibidas group by articulo_id, contenido
),
previos as (
  select articulo_id, contenido, veces,
         lag(contenido) over (partition by articulo_id order by contenido) as previo
    from valores
),
saltos as (
  select articulo_id, contenido, veces, previo,
         (contenido - previo) / nullif(previo, 0) as salto,
         max((contenido - previo) / nullif(previo, 0))
           over (partition by articulo_id) as salto_max
    from previos
)
select a.nombre as articulo,
       coalesce(a.unidad_compra, 'kilo') as MAGNITUD,
       count(*) as valores,
       sum(s.veces) as compras,
       min(s.contenido) as minimo,
       max(s.contenido) as maximo,
       round(100 * max(coalesce(s.salto, 0)), 0) as salto_max_pct,
       max(case when s.salto = s.salto_max
                then s.previo || ' -> ' || s.contenido end) as donde_salta,
       1 + count(*) filter (where s.salto > 0.15) as racimos_15,
       1 + count(*) filter (where s.salto > 0.25) as racimos_25,
       1 + count(*) filter (where s.salto > 0.40) as racimos_40,
       (select count(distinct articulo_id) from recibidas) as ARTS_EN_LA_VENTANA,
       (select max(procesada_el)::date from compras
         where estado = 'recepcionado') as TESTIGO_ultima_recepcion
  from saltos s
  join articulos a on a.id = s.articulo_id
 group by a.nombre, a.unidad_compra, s.articulo_id
 order by racimos_25 desc, salto_max_pct desc, a.nombre;

-- Mide la FORMA y no la distancia: `racimos_25` es en cuantas pilas quedaria
-- el articulo con un corte del 25%, y los tres umbrales van al lado para
-- elegir. MAGNITUD viene en la fila porque el contenido esta expresado en
-- `unidad_compra`: adentro de un articulo es siempre la misma, asi que Mango
-- no puede salir partido en dos pilas que son una.
-- Ver docs/separar_las_cajas_por_kilaje.md
