-- LOS MISMOS MOTIVOS, PERO POR VENTANA DE BÚSQUEDA. El total de vino_armada_1
-- es de TODA la historia y Buscar Compras muestra 48hs por defecto: el 67% del
-- corte puede ser cierto sobre la población y cero sobre la pantalla.
--
-- Cada fila es un rango de los que alguien pide de verdad. `ofrecidas` es la
-- población de esa ventana, y sin ella los otros números no se pueden leer.
with c0 as (select fecha from corte_modelo where id = 1),
v (etiqueta, dias) as (
  values ('48hs (lo que muestra por defecto)', 1),
         ('7 dias', 7), ('30 dias', 30), ('90 dias', 90), ('todo', 100000)
)
select v.etiqueta,
       (select fecha from c0)                                   as corte,
       count(c.id)                                              as ofrecidas,
       count(c.id) filter (
         where (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
               <= (select fecha from c0))                       as frenaria_el_corte,
       count(c.id) filter (where cons.bultos > 0)               as con_lote_ya_consumido,
       count(c.id) filter (
         where cons.bultos >= coalesce(c.cantidad_cajones_real, c.cantidad_cajones))
                                                                as consumido_entero,
       count(c.id) filter (
         where (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
               > (select fecha from c0)
           and cons.bultos < coalesce(c.cantidad_cajones_real, c.cantidad_cajones))
                                                                as se_puede_marcar
  from v
  left join compras c
    on c.estado = 'recepcionado'
   and c.ficha_en_origen_id is null
   and c.fecha_operacion >= current_date - v.dias
  left join lateral (
    select coalesce(sum(rc.bultos), 0) as bultos
      from reprocesos_consumos rc
      join reprocesos r on r.id = rc.reproceso_id
     where rc.origen = 'compra' and rc.compra_id = c.id and r.anulado_el is null
  ) cons on true
 group by v.etiqueta, v.dias
 order by v.dias;
