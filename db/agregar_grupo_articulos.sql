-- Agrega grupo a articulos: clasificación del artículo (fruta, hortaliza,
-- y a futuro otros grupos), para poder separar listados/PDF por grupo.
--
-- Nullable y SIN check: los ~30 artículos existentes se clasifican después
-- de correr esto (no todos de una), y la lista de valores válidos vive en
-- el código (GRUPOS_ARTICULO_VALIDOS en app/main.py), no acá — así se
-- puede ampliar a futuro (ej. sumar "Almacén") con solo un cambio de
-- código y redeploy, sin volver a migrar la base.
--
-- Es un dato de clasificación, no afecta ningún cálculo de costeo,
-- precio sugerido o negociación.
--
-- Seguro de correr más de una vez (add column if not exists).

alter table articulos add column if not exists grupo text;

comment on column articulos.grupo is 'Clasificación del artículo (fruta, hortaliza, ...) — solo para separar listados, no afecta ningún cálculo. Sin CHECK: la lista de valores válidos vive en el código (GRUPOS_ARTICULO_VALIDOS) para poder ampliarla sin migrar la base.';
