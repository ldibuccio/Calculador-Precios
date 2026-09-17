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
-- LO QUE LA PREGUNTA DEL 17/09 NO CIERRA. La pantalla de Reproceso ya exige
-- decir en que caja quedo armada, asi que `normales_sin_declarar` deja de
-- crecer desde hoy. Quedan DOS cosas y esta consulta las dimensiona:
--
--   EN_ORIGEN_sin_declarar   la compra que llega YA ARMADA genera su guia R
--                            sola, y ahi NO HAY A QUIEN PREGUNTARLE. Con
--                            ficha variable queda en NULL igual que antes.
--                            Negarse ahi seria una pared en un camino frio.
--   compras_armadas_SIN_ENVASE  el selector de "viene armada en caja nuestra"
--                            ofrece TODAS las fichas del articulo, incluidas
--                            las de envase perdido. Marcar una ahi es una
--                            contradiccion que nadie frena.
--
-- `compras_armadas_EN_FICHA_VARIABLE` es el techo del primero: sin una sola,
-- el agujero de en_origen no existe hoy y no hay nada que construir.
