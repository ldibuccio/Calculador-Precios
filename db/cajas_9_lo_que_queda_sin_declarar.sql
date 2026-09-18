with base as (
  select min(fecha_operacion) as f
    from movimientos_envase
   where origen = 'conteo_inicial' and anulado_el is null
)
select count(*) filter (where r.tipo = 'en_origen'
                          and r.lleva_caja_nuestra is null)      as EN_ORIGEN_sin_declarar,
       count(*) filter (where r.tipo = 'en_origen')              as en_origen_total,
       count(*) filter (where r.tipo = 'normal'
                          and r.lleva_caja_nuestra is null)      as normales_sin_declarar,
       count(*) filter (where r.tipo = 'normal')                 as normales_total,
       (select count(*) from fichas_logistica
         where envase_variable is true)                          as fichas_VARIABLES,
       (select count(*) from compras c
          join fichas_logistica f on f.id = c.ficha_en_origen_id
         where f.envase_variable is true)                        as compras_armadas_EN_FICHA_VARIABLE,
       (select count(*) from compras c
          join fichas_logistica f on f.id = c.ficha_en_origen_id
         where f.envase_id is null)                              as compras_armadas_SIN_ENVASE,
       (select f from base)                                      as desde_el_conteo,
       max(r.fecha_operacion)                                    as TESTIGO_ultima_guia
  from reprocesos r cross join base b
 where r.anulado_el is null
   and b.f is not null
   and r.fecha_operacion >= b.f;

-- ---------------------------------------------------------------------------
-- CUANTAS GUIAS R NO DICEN EN QUE CAJA SE ARMARON, y por que camino.
--
-- CONTESTA OTRA COSA DESDE EL 18/09. Se escribio para dimensionar el agujero
-- de `en_origen` —la compra que llega ya armada genera su guia R sola— y ese
-- agujero SE CERRO SIN CONSTRUIR NADA: la caja sale de la ficha, asi que la
-- guia en origen la deriva igual que las normales.
--
-- Lo que contesta hoy: CUANTAS FILAS VIEJAS quedan en NULL. Son de dos clases
-- y las dos se arreglan derivando de la ficha:
--
--   anteriores al 16/09   la columna no existia y la migracion no backfillea
--   ficha VARIABLE        la regla vieja las trataba como "hay que preguntar"
--
-- `compras_armadas_SIN_ENVASE` es otra cosa y sigue viva: compras marcadas
-- "viene en caja nuestra" contra una ficha de envase perdido, que no tiene
-- ninguna. El selector dejo de ofrecerlas y la escritura las rechaza; esta
-- columna cuenta las que ya estaban.
