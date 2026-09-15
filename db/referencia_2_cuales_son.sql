-- LOS CONTADOS, UNO POR UNO, PARA DECIDIR CADA REFERENCIA A MANO.
--
-- `referencia` está expresada en `unidad_compra`, NO en kilos: un 40 en un
-- artículo con unidad_compra='unidad' son cuarenta unidades por cajón. Clavar
-- la referencia en kilos re-etiquetaría ese número sin moverlo.
--
-- `kilos_por_cajon` es lo que haría falta para poder clavarla, y viene con su
-- DENOMINADOR al lado (`compras_con_kilos` sobre `compras`): un artículo
-- contado solo tiene kilos en las compras cargadas con el modelo de las dos
-- magnitudes (desde el 15/09). Con `compras_con_kilos 0` ese promedio es NULL
-- y el número no existe en la base — habría que preguntarlo en el galpón, no
-- deducirlo. Un NULL ahí y un 0 significan cosas distintas.
select
    a.nombre,
    a.unidad_compra                          as magnitud_de_la_referencia,
    a.unidad_conteo,
    a.contenido_referencia                   as referencia,
    count(c.id)                              as compras,
    count(coalesce(c.cantidad_kilos_real, c.cantidad_kilos))
                                             as compras_con_kilos,
    round(avg(coalesce(c.cantidad_kilos_real, c.cantidad_kilos)
              / nullif(coalesce(c.cantidad_cajones_real, c.cantidad_cajones), 0)), 2)
                                             as kilos_por_cajon,
    max(c.cargado_el)::date                  as ultima_compra
from articulos a
left join compras c on c.articulo_id = a.id
where a.activo
  and a.unidad_compra is distinct from 'kilo'
group by a.nombre, a.unidad_compra, a.unidad_conteo, a.contenido_referencia
order by a.nombre;
