with v as (select current_date - 90 as desde),
guias as (
  select r.id, r.articulo_id, r.fecha_operacion, r.bultos_tomados,
         count(*) over (partition by r.articulo_id, r.fecha_operacion) as del_dia
    from reprocesos r, v
   where r.anulado_el is null and r.tipo = 'normal'
     and r.fecha_operacion >= v.desde
)
select count(*) filter (where del_dia > 1)                      as comparten_dia,
       count(*)                                                 as guias_en_la_ventana,
       count(distinct (articulo_id, fecha_operacion))
         filter (where del_dia > 1)                             as dias_con_varias,
       round(coalesce(sum(bultos_tomados) filter (where del_dia > 1), 0), 2)
                                                                as bultos_en_riesgo,
       round(coalesce(sum(bultos_tomados), 0), 2)               as bultos_totales,
       coalesce(max(del_dia), 0)                                as peor_dia,
       (select desde from v)                                    as desde,
       (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r
  from guias;

-- ---------------------------------------------------------------------------
-- EL TECHO DEL REBOTE. Si el freno pasa a contar las salidas del MISMO DIA,
-- la unica guia que puede cambiar de resultado es la que comparte articulo y
-- fecha con otra: una guia sola en su dia ve exactamente los mismos lotes
-- antes y despues. `comparten_dia` es ese techo, y `guias_en_la_ventana` su
-- poblacion — la resta se hace en la misma fila.
--
-- NO dice cuantas se rebotarian: dice cuantas PUEDEN. Saber cuantas de verdad
-- exige rejugar el FIFO por guia, que no se hace en SQL. El techo alcanza para
-- decidir si vale la pena preocuparse.
--
-- `peor_dia` es cuantas guias cayeron el mismo dia sobre el mismo articulo: el
-- agujero NO esta acotado a dos — cada guia del dia ve el lote entero, asi que
-- con tres se puede tomar tres veces lo que habia.
