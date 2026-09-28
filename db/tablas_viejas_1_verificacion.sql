select 'tablas_viejas_1' as QUE_MIGRACION,
       count(*) filter (where c.relname in ('recepciones', 'aprendizaje_proveedores',
         'pedidos_supermercado', 'precios_dia', 'resultados')) as quedan_de_las_5,
       count(*) as tablas_total,
       (select max(procesada_el)::date from compras where estado = 'recepcionado') as ultima_recepcion
from pg_class c
join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
where c.relkind = 'r';

-- Verificación de tablas_viejas_1, APARTE del `do`. Resultado bueno:
-- quedan_de_las_5 0 en las dos bases, y tablas_total 68 en Frutamax (73 - 5)
-- y 64 en Palmala (no cambia). ultima_recepcion dice de qué base es la fila.
