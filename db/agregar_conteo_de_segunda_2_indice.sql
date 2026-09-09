-- BLOQUE 2 — el índice, que es lo que impide que un conteo tape al otro.
--
-- Va aparte del bloque 1 y no pegado abajo: los bloques largos se truncan
-- en el editor, y cada uno tiene que poder correrse y fallar solo.
--
-- El DISTINCT ON del Cotejo agrupa por PORCIÓN, y la porción ahora son tres
-- claves. Sin `es_segunda` adentro, el conteo de segunda y el de sueltos del
-- mismo artículo compiten por el mismo renglón —los dos tienen ficha_id
-- NULL— y el último cargado tapa al otro sin decir nada.
do $$
begin
    drop index if exists conteos_stock_cotejo_idx;
    create index conteos_stock_cotejo_idx
        on conteos_stock (articulo_id, ficha_id, es_segunda, creado_en desc);

    comment on column conteos_stock.es_segunda is
        'true = el conteo es del POOL DE SEGUNDA del artículo, que no tiene ficha (por eso el check conteos_stock_segunda_sin_ficha). false con ficha_id = las cajas de esa ficha; false con ficha_id NULL = los bultos sueltos. Las tres porciones que lista el Remanente, y la clave del DISTINCT ON del Cotejo.';
end $$;
