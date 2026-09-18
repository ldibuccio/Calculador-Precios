with base as (
  select min(fecha_operacion) as f
    from movimientos_envase
   where origen = 'conteo_inicial' and anulado_el is null
)
select 'cajas_11' as QUE_MIGRACION,
  count(*) filter (where r.lleva_caja_nuestra is null
                          and r.ficha_id is not null)              as sin_declarar_CON_ficha,
       count(*) filter (where r.lleva_caja_nuestra is null
                          and r.ficha_id is null)                  as sin_ficha_se_quedan,
       count(*) filter (where r.lleva_caja_nuestra is true)         as declaradas_CON_caja,
       count(*) filter (where r.lleva_caja_nuestra is false)        as declaradas_SIN_caja,
       count(*)                                                     as guias_POBLACION,
       (select f from base)                                         as desde_el_conteo,
       max(r.fecha_operacion)                                       as TESTIGO_ultima_guia
  from reprocesos r cross join base b
 where r.anulado_el is null
   and r.tipo <> 'inicial'
   and b.f is not null
   and r.fecha_operacion >= b.f;

-- ---------------------------------------------------------------------------
-- SE CORRE EN OTRA CORRIDA, NUNCA PEGADA AL `do`: el editor se queda con la
-- ultima y el bloque no se ejecuta, sin error y con "no rows", que es
-- exactamente la salida normal de un `do` que si corrio.
--
-- `sin_declarar_CON_ficha` tiene que dar 0 despues del backfill. Ese es el
-- numero del arreglo.
--
-- `sin_ficha_se_quedan` NO tiene que dar 0 y no es una falla: una guia sin
-- ficha no tiene de donde derivar el envase, y su arreglo es asignarle la
-- ficha desde Guias R, que vuelve a derivar sola.
--
-- Las dos `declaradas_*` son el control: sin ellas, un 0 en la primera se
-- lee igual viniendo de un backfill que corrio que de uno que no encontro
-- nada — y la poblacion al lado dice contra cuanto se esta contando.
