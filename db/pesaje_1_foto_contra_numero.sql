-- ¿Depósito PESA y no lo carga, o directamente no pesa?
--
-- `kilos_4` dijo que 346 de 421 recepciones se aceptaron SIN TOCAR el
-- numero precargado. Eso no dice cual de las dos cosas pasa, y la
-- diferencia es todo: si pesan y no lo cargan, falta un paso de carga; si
-- no pesan, falta una balanza o un habito, y ninguna pantalla lo arregla.
--
-- LA FOTO DE LA BALANZA LO SEPARA, porque se saca ANTES de apretar Recibir
-- (deposito_recepcion.html: pesar, foto, recibir):
--     foto SI + sin tocar -> fueron a la balanza y aceptaron el estimado
--     foto NO + sin tocar -> ninguna evidencia de que hayan pesado
--     foto SI + tocada    -> el camino completo
--     foto NO + tocada    -> cambiaron el numero sin sacar la foto
--
-- Y `foto_despues`: si la foto se sube DESPUES de `procesada_el` no dice
-- nada del numero que se cargo -- se saco con el dato ya escrito.
--
-- Conteos con su POBLACION al lado y los dos testigos.
with p as (
  select c.id, c.procesada_el,
         (c.contenido_por_cajon_real = c.contenido_por_cajon
          and coalesce(c.cantidad_cajones_real, c.cantidad_cajones) = c.cantidad_cajones) as sin_tocar,
         (select min(f.creado_en) from fotos_recepcion f where f.compra_id = c.id) as foto_el
  from compras c
  where c.estado = 'recepcionado'
    and c.contenido_por_cajon_real is not null
    and c.fecha_operacion >= current_date - 60
)
select count(*)                                                       as recepciones,
       count(*) filter (where sin_tocar)                              as sin_tocar,
       count(*) filter (where not sin_tocar)                          as tocadas,
       count(*) filter (where foto_el is not null)                    as con_foto,
       count(*) filter (where sin_tocar and foto_el is not null)      as sin_tocar_con_foto,
       count(*) filter (where sin_tocar and foto_el is null)          as sin_tocar_sin_foto,
       count(*) filter (where not sin_tocar and foto_el is not null)  as tocada_con_foto,
       count(*) filter (where not sin_tocar and foto_el is null)      as tocada_sin_foto,
       count(*) filter (where foto_el is not null
                          and procesada_el is not null
                          and foto_el > procesada_el)                 as foto_despues,
       max(procesada_el)::date                                        as ultima_recepcion,
       max(foto_el)::date                                             as ultima_foto
from p;
