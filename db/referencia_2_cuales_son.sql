-- LOS CONTADOS, UNO POR UNO, PARA DECIDIR CADA REFERENCIA A MANO.
--
-- BASELINE AL 15/09 — los cuatro tienen su referencia en la magnitud de
-- CONTEO y NINGUNO tiene kilaje observado (todas sus compras son anteriores
-- al modelo de las dos magnitudes, que arrancó ese día):
--
--   FRUTAMAX  Arandano cubeta/cubeta ref 12 · 14 compras · 0 con kilos
--             Frutilla cubeta/cubeta ref  8 ·  8 compras · 0 con kilos
--             Mango    unidad/unidad ref null · 27 compras · 0 con kilos
--             Palta    unidad/unidad ref  80 · 28 compras · 0 con kilos
--   PALMALA   los mismos cuatro · 0 o 1 compra · 0 con kilos
--
-- Por eso NO se clavó la referencia en kilos: no re-etiquetaría esos números,
-- los dejaría SIN referencia. Cómo leerla cuando vuelva a correrse, al pie.

select
    a.nombre,
    a.unidad_compra                          as magnitud_de_la_referencia,
    a.unidad_conteo,
    a.contenido_referencia                   as referencia,
    count(c.id)                              as compras,
    count(coalesce(c.cantidad_kilos_real, c.cantidad_kilos))
                                             as compras_con_kilos,
    count(distinct c.proveedor_id) filter (
        where coalesce(c.cantidad_kilos_real, c.cantidad_kilos) is not null)
                                             as proveedores_distintos,
    round(min(coalesce(c.cantidad_kilos_real, c.cantidad_kilos)
              / nullif(coalesce(c.cantidad_cajones_real, c.cantidad_cajones), 0)), 2)
                                             as kilos_min,
    round(percentile_cont(0.5) within group (
              order by coalesce(c.cantidad_kilos_real, c.cantidad_kilos)
                       / nullif(coalesce(c.cantidad_cajones_real, c.cantidad_cajones), 0)
          )::numeric, 2)                     as kilos_mediana,
    round(max(coalesce(c.cantidad_kilos_real, c.cantidad_kilos)
              / nullif(coalesce(c.cantidad_cajones_real, c.cantidad_cajones), 0)), 2)
                                             as kilos_max,
    max(c.cargado_el)::date                  as ultima_compra
from articulos a
left join compras c on c.articulo_id = a.id
where a.activo
  and a.unidad_compra is distinct from 'kilo'
group by a.nombre, a.unidad_compra, a.unidad_conteo, a.contenido_referencia
order by a.nombre;

-- CÓMO SE LEE CUANDO VUELVA A CORRERSE, y es lo que evita decidir con un
-- promedio: la pregunta NO es "¿cuánto pesa el cajón?" sino "¿hay UN valor
-- dominante?". Eso lo contesta el RANGO, no el centro. `kilos_min` y
-- `kilos_max` pegados a la mediana son lo único que distingue un artículo de
-- un formato —donde precargar acierta casi siempre— de uno multiformato,
-- donde la mediana devuelve el formato que más vino en la ventana y se mueve
-- sola cuando cambia la mezcla de proveedores.
--
-- Y `compras_con_kilos` es el denominador: un NULL en la mediana con 0 al
-- lado significa "el número no existe en la base", no "da cero".
--
-- `proveedores_distintos` es el otro denominador, y decide si el conteo vale:
-- cinco compras al MISMO puesto en la misma semana pueden ser cinco veces el
-- mismo formato por una razón estructural —ese proveedor trae ése— y entonces
-- son más parecidas a UNA observación que a cinco. Lo que agrega información
-- es lo que CAMBIA entre una compra y la siguiente, no cuántas son.
--
-- DOS YA ESTÁN CONTESTADOS SIN DATOS, y ninguna cantidad de compras los
-- cambia: **Mango es multiformato** (cajas de 40, 12 y 10, preguntado en el
-- galpón) y por eso su referencia ya está vacía; **Arandano y Frutilla vienen
-- en CUBETAS**, que es un recipiente —cuánto entra depende de cómo se llene—
-- así que su rango puede no cerrarse nunca.
