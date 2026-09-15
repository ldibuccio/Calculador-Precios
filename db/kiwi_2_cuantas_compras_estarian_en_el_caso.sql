-- kiwi_2 · ¿CUÁNTAS COMPRAS estarían en el caso multiunidad?
--
-- kiwi_1 cuenta ARTÍCULOS y pares; ésta cuenta COMPRAS, que es la unidad en
-- la que habría que cargar la segunda magnitud. Son dos cuentas distintas y
-- la segunda es la que dice cuánto trabajo nuevo es: tres artículos pueden
-- ser el 40% de las compras si son los que más se compran.
--
-- multiunidad = el artículo tiene fichas que NO se ponen de acuerdo entre sí
-- (un cliente por kilo y otro por unidad). Es el caso donde la conversión
-- hace falta de verdad; el resto se arregla cargando bien una cosa.
--
-- UNA fila siempre, con la población al lado (corolario 45) y el testigo de
-- actividad (corolario 24). Correr en LAS DOS bases y pegar LAS DOS filas
-- con el nombre de la base adelante.
with multiunidad as (
    select a.id
    from articulos a
    join fichas_logistica f on f.articulo_id = a.id
    where a.unidad_compra is not null
    group by a.id
    having count(distinct f.unidad_venta) > 1
)
select
    count(*)                                                         as compras_90d,
    count(*) filter (where c.articulo_id in (select id from multiunidad))
                                                                     as compras_multiunidad,
    count(distinct c.articulo_id)                                    as arts_comprados_90d,
    count(distinct c.articulo_id) filter
        (where c.articulo_id in (select id from multiunidad))         as arts_multiunidad_comprados,
    (select count(*) from multiunidad)                               as arts_multiunidad_total,
    -- Lo que YA tendría la segunda magnitud cargada de casualidad: hoy es
    -- imposible (una de las dos columnas va NULL por construcción), así que
    -- esto tiene que dar 0 — y si da otra cosa, el supuesto está mal.
    count(*) filter (where c.cantidad_kilos is not null
                       and c.cantidad_fraccion is not null)          as con_las_dos_ya,
    max(c.fecha_operacion)                                           as ultima_compra
from compras c
where c.fecha_operacion >= current_date - 90;
