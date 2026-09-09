-- Sacar UNA foto de balanza: la fila de fotos_recepcion y el archivo del
-- bucket. NO borra la compra.
--
-- No es un script de un solo uso. No hay ningún botón en la pantalla que
-- borre una foto de balanza sola —el único camino que devuelve la ruta
-- para sacarla del Storage es borrar la COMPRA entera— así que éste es EL
-- camino mientras ese botón no exista. Estrenado el 08/09 sacando la foto
-- que dejó la prueba en Palmala (compra 181).
--
-- Son TRES pasos y el del medio NO es SQL: el archivo del Storage se borra
-- a mano desde el panel de Supabase, porque no hay ninguna ruta en la app
-- que borre una foto de balanza sola (el único camino que devuelve la ruta
-- para sacarla del bucket es borrar la COMPRA entera, y eso acá sobra).
--
-- El orden importa: si se borra la fila primero, la ruta se pierde y el
-- archivo queda en el bucket sin nada que lo nombre. Nadie lo va a
-- encontrar nunca. Por eso primero se LEE, después se borra el archivo, y
-- recién al final la fila.

-- ===== PASO 1 — leer, y ver qué más dejó la prueba (solo lectura) =====
-- La ruta que sale acá es la que hay que borrar en el panel de Storage,
-- bucket "comandas". Y de paso se mira el estado de la compra: si la
-- prueba la dejó RECEPCIONADA, eso es un movimiento de stock de verdad en
-- Palmala y es otra cosa a decidir, aparte de la foto.
select f.id            as fila_a_borrar,
       f.foto_ruta     as archivo_a_borrar_del_bucket,
       f.creado_en     as foto_sacada_el,
       c.id            as compra_id,
       a.nombre        as articulo,
       c.fecha_operacion,
       c.estado        as estado_de_la_compra,
       c.procesada_el  as recepcionada_el
from fotos_recepcion f
join compras c on c.id = f.compra_id
join articulos a on a.id = c.articulo_id
order by f.id;

-- ===== PASO 2 — NO ES SQL =====
-- Panel de Supabase > Storage > bucket "comandas" > la carpeta de la fecha
-- que diga la ruta del paso 1 > borrar ESE archivo.
-- Recién con el archivo borrado se corre el paso 3.

-- ===== PASO 3 — borrar la fila, y solo esa =====
-- La ruta va escrita a mano, copiada del paso 1: sin eso, un DELETE sobre
-- fotos_recepcion sin where borraría todas las que hubiera. La guarda
-- aborta si no tocó exactamente una fila -- si tocó 0, la ruta se copió
-- mal o la fila ya no está, y en los dos casos hay que mirar antes de
-- volver a correr.
do $$
declare
  ruta text := 'PEGAR-ACA-LA-RUTA-DEL-PASO-1';
  tocadas int;
begin
  -- La guarda NO compara contra el texto de arriba, y eso lo encontro
  -- probarlo: un buscar-y-reemplazar GLOBAL cambia el placeholder en los
  -- dos lados y la comparacion vuelve a dar true -- la guarda saltaria
  -- con la ruta buena puesta. Se pide que la ruta TENGA FORMA de ruta,
  -- que es algo que el placeholder no cumple nunca y una real siempre.
  if ruta !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}/.+\.[a-z]+$' then
    raise exception 'Eso no es una ruta del bucket, pega la del paso 1: %', ruta;
  end if;
  delete from fotos_recepcion where foto_ruta = ruta;
  get diagnostics tocadas = row_count;
  if tocadas <> 1 then
    raise exception 'Se esperaba borrar 1 fila y se borraron %: no se toca nada', tocadas;
  end if;
end $$;

-- ===== PASO 4 — verificación (solo lectura) =====
-- Conteos y UNA fila, con el testigo de actividad al lado: en una base
-- parada el cero de arriba no dice nada por sí solo.
select (select count(*) from fotos_recepcion)                              as fotos_de_balanza,
       (select count(*) from compras where estado = 'recepcionado')        as recepcionadas,
       (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion;
