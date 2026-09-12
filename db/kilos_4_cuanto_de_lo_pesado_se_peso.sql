-- ¿Cuánto de "lo que Depósito pesó" se pesó de verdad?
--
-- RECEPCIÓN PRECARGA LOS DOS CAMPOS REALES CON EL ESTIMADO
-- (deposito_recepcion.html), así que apretar "Recibir" sin tocar nada graba
-- real = estimado — "pesó exactamente lo que se había cargado". Y el
-- ingreso directo escribe el mismo valor en las dos columnas por
-- construcción. En los dos casos la referencia vuelve como evidencia de que
-- la referencia estaba bien.
--
-- EXCLUIR SOLO EL INGRESO DIRECTO mide mal: su motivo (escribe las dos
-- columnas) no es el motivo del problema (el real puede ser igual al
-- estimado sin que nadie pese). Lo que separa es `sin_tocar`.
--
-- Las columnas van DE A PARES —todas contra tocadas— en la misma fila.
-- `tocadas 0` es el caso extremo: de ese artículo solo se sabe que nadie
-- cambió el número. Ésos salen PRIMERO. Verificada con el caso plantado y
-- el canario de sin_tocar; el detalle está en el commit.
with p as (
  select c.articulo_id, c.contenido_por_cajon_real as real_kg,
         (c.contenido_por_cajon_real = c.contenido_por_cajon
          and coalesce(c.cantidad_cajones_real, c.cantidad_cajones) = c.cantidad_cajones) as sin_tocar,
         (c.retiro_origen = 'ingreso_directo') as directo
  from compras c
  where c.estado = 'recepcionado'
    and c.contenido_por_cajon_real is not null
    and c.fecha_operacion >= current_date - 60
)
select a.id, a.nombre as articulo, a.contenido_referencia as referencia,
       count(*) as recepciones,
       count(*) filter (where p.directo) as ingreso_directo,
       count(*) filter (where p.sin_tocar) as sin_tocar,
       count(*) filter (where not p.sin_tocar) as tocadas,
       round(avg(p.real_kg), 2) as promedio_todas,
       round(percentile_cont(0.5) within group (order by p.real_kg)::numeric, 2) as mediana_todas,
       round(avg(p.real_kg) filter (where not p.sin_tocar), 2) as promedio_tocadas,
       round(avg(p.real_kg) - a.contenido_referencia, 2) as desvio_todas,
       round(avg(p.real_kg) filter (where not p.sin_tocar) - a.contenido_referencia, 2) as desvio_tocadas,
       (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion
from articulos a
join p on p.articulo_id = a.id
where a.contenido_referencia is not null
group by a.id, a.nombre, a.contenido_referencia
having count(*) >= 2
order by abs(coalesce(avg(p.real_kg) filter (where not p.sin_tocar), 0) - avg(p.real_kg)) desc,
         count(*) filter (where p.sin_tocar) desc;
