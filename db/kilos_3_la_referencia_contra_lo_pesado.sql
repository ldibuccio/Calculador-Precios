-- ¿La referencia del artículo se parece a lo que viene pesando? Decide si
-- hay que arreglar la CARGA antes que el aviso.
--
-- El contenido estimado de una compra NO lo tipea el comprador: lo precarga
-- el sistema desde articulos.contenido_referencia, en los cuatro caminos
-- (el form manual por JS, y foto/listado/múltiples por _contenido_referencia_de
-- en app/main.py). O sea que un estimado sistemáticamente mal no es una carga
-- descuidada: es una referencia vieja que el sistema sigue sugiriendo.
--
-- La MEDIANA al lado del promedio a propósito: una sola recepción mal
-- cargada mueve el promedio y no mueve la mediana, así que cuando los dos
-- se separan el que hay que mirar es el caso, no el artículo.
--
-- `recepciones` es la POBLACIÓN de cada fila: una diferencia sobre dos
-- pesadas no dice nada y sobre veinte sí. Sin esa columna, las dos filas
-- se leen igual.
-- Verificada contra db/esquema_completo.sql en Postgres 16 con el caso
-- plantado (seis artículos: uno desviado +2,5, uno justo en 0, uno abajo
-- -2,1, uno con una sola pesada, uno con un outlier y uno sin referencia) y
-- el canario de la ventana. El detalle está en el commit.
with pesadas as (
  select c.articulo_id, c.contenido_por_cajon_real as real_kg
  from compras c
  where c.estado = 'recepcionado'
    and c.contenido_por_cajon_real is not null
    and c.fecha_operacion >= current_date - 60
)
select a.id, a.nombre as articulo, a.unidad_compra as unidad,
       a.contenido_referencia as referencia,
       count(p.real_kg) as recepciones,
       round(avg(p.real_kg), 2) as promedio_real,
       round(percentile_cont(0.5) within group (order by p.real_kg)::numeric, 2) as mediana_real,
       round(min(p.real_kg), 2) as minimo,
       round(max(p.real_kg), 2) as maximo,
       round(avg(p.real_kg) - a.contenido_referencia, 2) as desvio,
       (select count(*) from articulos where contenido_referencia is not null) as arts_con_referencia,
       (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion
from articulos a
join pesadas p on p.articulo_id = a.id
where a.contenido_referencia is not null
group by a.id, a.nombre, a.unidad_compra, a.contenido_referencia
having count(p.real_kg) >= 2
order by abs(avg(p.real_kg) - a.contenido_referencia) desc;
