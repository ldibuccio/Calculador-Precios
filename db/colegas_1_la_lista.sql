do $$
begin
  create table if not exists colegas (
      id                 bigint generated always as identity primary key,
      nombre             text not null,
      nombre_normalizado text not null unique,
      activo             boolean not null default true,
      creado_en          timestamptz not null default now()
  );

  if not exists (select 1 from information_schema.tables
                  where table_schema = 'public' and table_name = 'colegas') then
    raise exception 'no quedo creada la tabla colegas';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 1 de 3. CORRE SOLO. Verificacion aparte (colegas_4).
--
-- LISTA APARTE de `proveedores`, y no es una preferencia: es el precedente
-- escrito de esta casa. `proveedores_puesto` dice textual "NO son los
-- proveedores de Compras: circuitos separados a proposito". Cuando el
-- circuito es otro, la lista es otra.
--
-- Lo que costaria reusar `proveedores`: un colega que no te vende nada
-- tendria que existir como proveedor, y entonces APARECE EN EL SELECTOR DE
-- CARGA DE COMPRAS. La unica forma de sacarlo de ahi es activo = false, que
-- ya significa otra cosa (baja logica por codigo mal tipeado). Dos
-- significados en la misma columna es como se rompe algo en seis meses.
--
-- `nombre_normalizado` es una COLUMNA y no un indice funcional, a proposito:
-- asi el plegado esta escrito UNA sola vez, en Python (normalizar_texto), y
-- el indice solo exige que lo que Python guardo sea distinto. Un indice que
-- pliegue por su cuenta serian DOS reglas, y ese es exactamente el caso de
-- "ruben" al lado de "Ruben" que ya nos costo caro.
--
-- `if not exists` sobre ESTRUCTURA esta bien: la tabla existe o no, y si
-- existe es la misma. La regla que lo prohibe es para CONTENIDO —una lista
-- de valores, un umbral— y eso vive en el bloque 3.
