-- Poder CONTAR la segunda. Se corre en las DOS bases, bloque por bloque.
--
-- Por qué hace falta: conteos_stock tenía DOS porciones y no tres. `ficha_id`
-- con valor son las cajas de esa ficha, y `ficha_id` NULL son los bultos
-- sueltos — el comentario de la columna lo dice así desde el corte. La
-- segunda no tiene ficha, así que un conteo suyo entraba como
-- (articulo, NULL) y PISABA al de sueltos. No es que faltara una pantalla:
-- no había dónde guardarlo.

-- BLOQUE 1 — la columna y su guarda.
do $$
begin
    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'conteos_stock'
          and column_name = 'es_segunda'
    ) then
        alter table conteos_stock
            add column es_segunda boolean not null default false;
    end if;

    -- La segunda NO tiene ficha. Una sola implicación cubre las DOS
    -- direcciones: si es_segunda entonces ficha_id es null, y por
    -- contrapositiva un conteo CON ficha nunca puede ser de segunda. Es la
    -- media regla del CHECK de pedidos_renglones, que prohibía "ficha sin
    -- artículo" y dejaba pasar el caso espejo.
    if not exists (
        select 1 from pg_constraint
        where conname = 'conteos_stock_segunda_sin_ficha'
    ) then
        alter table conteos_stock
            add constraint conteos_stock_segunda_sin_ficha
            check (not es_segunda or ficha_id is null);
    end if;
end $$;
