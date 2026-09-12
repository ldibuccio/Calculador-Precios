-- kilos_3 otra vez, EXCLUYENDO el ingreso directo, para ver cuánto de los
-- desvíos en cero era la referencia confirmándose a sí misma por ese camino.
--
-- El ingreso directo escribe contenido_por_cajon en las DOS columnas, la
-- estimada y la real (ver _insertar_compra_con_guia), porque la compra nace
-- recepcionada. Así que ahí el "real" es la referencia por construcción.
--
-- MIDE UN SOLO FACTOR, y no el problema entero: Recepción también precarga
-- los dos campos reales con el estimado, así que aceptar sin tocar graba
-- real = estimado por el camino NORMAL. Para eso está kilos_4, que separa
-- por si alguien CAMBIÓ el número. Ésta contesta nada más "¿cuánto pesaba
-- el ingreso directo?" — si los ceros no se mueven acá, la contaminación
-- está en Recepción y no en este camino.
--
-- Las dos columnas van EN LA MISMA FILA, con y sin, para no tener que
-- comparar este resultado contra el de kilos_3 de memoria.
--
-- Verificada contra el esquema real con el caso plantado; el detalle está
-- en el commit.
with p as (
  select c.articulo_id, c.contenido_por_cajon_real as real_kg,
         (c.retiro_origen is distinct from 'ingreso_directo') as no_directo
  from compras c
  where c.estado = 'recepcionado'
    and c.contenido_por_cajon_real is not null
    and c.fecha_operacion >= current_date - 60
)
select a.id, a.nombre as articulo, a.contenido_referencia as referencia,
       count(*) as recepciones,
       count(*) filter (where not p.no_directo) as ingreso_directo,
       count(*) filter (where p.no_directo) as sin_directo,
       round(avg(p.real_kg), 2) as promedio_todas,
       round(avg(p.real_kg) filter (where p.no_directo), 2) as promedio_sin_directo,
       round(avg(p.real_kg) - a.contenido_referencia, 2) as desvio_todas,
       round(avg(p.real_kg) filter (where p.no_directo) - a.contenido_referencia, 2) as desvio_sin_directo,
       (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion
from articulos a
join p on p.articulo_id = a.id
where a.contenido_referencia is not null
group by a.id, a.nombre, a.contenido_referencia
having count(*) >= 2
order by abs(coalesce(avg(p.real_kg) filter (where p.no_directo), 0) - avg(p.real_kg)) desc,
         count(*) filter (where not p.no_directo) desc;
