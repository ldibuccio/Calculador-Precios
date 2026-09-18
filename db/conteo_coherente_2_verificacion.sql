-- VERIFICACIÓN de db/conteo_coherente_1_migracion.sql.
--
-- Se corre DESPUÉS del bloque, en las DOS bases, y se pegan las DOS filas con
-- el nombre de la base adelante (corolario 17): salen idénticas por diseño
-- salvo el testigo, y eso es lo esperado.
--
-- `guarda` cuenta POR NOMBRE, que es lo único que sirve: un "¿existe algún
-- check en articulos?" daría 1 con el constraint viejo puesto y taparía el caso.
--
-- Lo que tiene que dar: guarda 1 · ofensores 0 · contados >= 0 · y el testigo
-- con una fecha. `contados` no es un problema: es la población contra la que
-- el check tiene algo que decir (corolario 45) — si diera 0, el check estaría
-- puesto y no podría rechazar nada, y eso hay que saberlo.
select 'conteo_coherente_2' as QUE_MIGRACION,
    (select count(*) from pg_constraint
      where conrelid = 'articulos'::regclass
        and conname = 'articulos_conteo_coherente')                     as guarda,
    count(*) filter (where coalesce(a.unidad_compra, 'kilo') <> 'kilo'
                       and a.unidad_conteo is not null
                       and a.unidad_conteo <> a.unidad_compra)          as ofensores,
    count(*) filter (where coalesce(a.unidad_compra, 'kilo') <> 'kilo') as contados,
    count(*)                                                            as articulos_activos,
    (select max(c.cargado_el)::date from compras c)                     as ultima_compra
from articulos a
where a.activo;
