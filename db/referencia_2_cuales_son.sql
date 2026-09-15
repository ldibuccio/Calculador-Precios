-- LAS FILAS DE LOS CONTADOS, UNA POR UNA. Se corre si `referencia_1` dijo que
-- hay alguno con referencia cargada: son pocos (4 en Frutamax al 15/09), así
-- que acá la lista sí se puede leer entera y decidir a mano cada número.
--
-- `referencia` está expresada en `unidad_compra`, NO en kilos. Un 40 en un
-- artículo con unidad_compra='unidad' son cuarenta unidades por cajón.
select
    a.nombre,
    a.unidad_compra                         as magnitud_de_la_referencia,
    a.unidad_conteo,
    a.contenido_referencia                  as referencia,
    count(c.id)                             as compras,
    max(c.cargado_el)::date                  as ultima_compra
from articulos a
left join compras c on c.articulo_id = a.id
where a.activo
  and a.unidad_compra is distinct from 'kilo'
group by a.nombre, a.unidad_compra, a.unidad_conteo, a.contenido_referencia
order by a.nombre;
