select count(*) filter (where c.ficha_en_origen_id is null)        as la_663_desmarcada,
       count(*) filter (where c.ficha_en_origen_id is not null)    as sigue_marcada,
       (select count(*) from reprocesos
         where compra_origen_id = 663 and anulado_el is null)      as guias_VIVAS_de_la_663,
       (select count(*) from reprocesos
         where compra_origen_id = 663)                             as guias_de_la_663,
       (select count(*) from compras t
          join fichas_logistica g on g.id = t.ficha_en_origen_id
         where g.envase_id is null)                                as marcadas_SIN_ENVASE_que_quedan,
       (select count(*) from compras t
          join fichas_logistica g on g.id = t.ficha_en_origen_id)  as POBLACION_marcadas
  from compras c
 where c.id = 663;

-- ---------------------------------------------------------------------------
-- SE CORRE EN OTRA CORRIDA, nunca pegada al `do`.
--
-- `la_663_desmarcada` tiene que dar 1 y `sigue_marcada` 0.
--
-- `guias_VIVAS_de_la_663` tiene que dar 0 — si da 1, el bloque de arriba
-- abortó y no escribió nada, que es lo correcto: falta anular la guía.
-- `guias_de_la_663` al lado dice que la anulada sigue ahi como registro.
--
-- `marcadas_SIN_ENVASE_que_quedan` es el numero de cajas_9 visto de cerca:
-- tiene que pasar de 1 a 0. Y la poblacion al lado dice contra cuanto se
-- esta contando — el filtro de 2770e7c impide que vuelva a crecer.
