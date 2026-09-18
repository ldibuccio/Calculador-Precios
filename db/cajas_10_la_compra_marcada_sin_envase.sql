select c.id                                as compra,
       c.fecha_operacion                   as fecha,
       a.nombre                            as articulo,
       p.nombre                            as proveedor,
       c.estado,
       c.cantidad_cajones_real             as cajones,
       f.id                                as ficha,
       cl.nombre                           as cliente,
       f.nombre_cliente                    as codigo_de_la_ficha,
       (select count(*) from fichas_logistica o
         where o.articulo_id = c.articulo_id
           and o.envase_id is not null)     as OTRAS_FICHAS_CON_ENVASE,
       (select count(*) from fichas_logistica o
         where o.articulo_id = c.articulo_id) as fichas_del_articulo,
       r.id                                as guia_r,
       r.lleva_caja_nuestra                as guia_lleva_caja,
       r.envase_id                         as guia_envase,
       (select count(*) from compras t
          join fichas_logistica g on g.id = t.ficha_en_origen_id) as POBLACION_marcadas
  from compras c
  join fichas_logistica f on f.id = c.ficha_en_origen_id
  join articulos a on a.id = c.articulo_id
  join proveedores p on p.id = c.proveedor_id
  left join clientes cl on cl.id = f.cliente_id
  left join reprocesos r on r.compra_origen_id = c.id and r.anulado_el is null
 where f.envase_id is null
 order by c.fecha_operacion desc;

-- ---------------------------------------------------------------------------
-- LA COMPRA MARCADA "VIENE ARMADA" CONTRA UNA FICHA DE ENVASE PERDIDO.
--
-- `compras_armadas_SIN_ENVASE` de cajas_9 dio 1 en Frutamax: esto dice CUAL.
-- El selector dejo de ofrecerlas y la escritura las rechaza (2770e7c); esta
-- es de antes del filtro.
--
-- LA COLUMNA QUE DECIDE ES `OTRAS_FICHAS_CON_ENVASE`, y separa los dos casos
-- que se ven iguales:
--
--   en 0   ningun cliente recibe este articulo en caja nuestra -> ENVASE
--          PERDIDO de verdad, y lo que esta mal es LA MARCA de la compra.
--   >= 1   otro cliente si lo recibe en caja -> el articulo se reenvasa, y
--          lo que falta es el `envase_id` de ESTA ficha.
--
-- `guia_lleva_caja` tiene que venir en `false` y `guia_envase` en NULL: asi
-- se derivo, y por eso el stock de cajas NO se movio. Si alguna viene en
-- `true`, eso es otra cosa y hay que mirarla antes de tocar nada.
