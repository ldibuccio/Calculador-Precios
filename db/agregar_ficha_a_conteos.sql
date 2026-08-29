-- ============================================================================
-- ETAPA 3 — El conteo físico dice de qué FICHA es lo que contó.
--
-- Hoy conteos_stock solo tiene articulo_id, así que un conteo de Banana es
-- "todo lo de Banana junto": los cajones sueltos más las cajas armadas de
-- todas las fichas, en un solo número. El Cotejo lo compara contra el
-- stock del artículo, que también es la suma de todo, y da. Pero cuando no
-- da, no hay forma de saber DÓNDE está la diferencia: si faltan cajones
-- sueltos o si faltan cajas de una ficha en particular.
--
-- Desde la etapa 1 el sistema sabe cuántas cajas se armaron para cada
-- ficha (reprocesos.ficha_id). Recién ahora existe el número contra el
-- cual comparar, y por eso esta etapa iba después de aquella.
--
-- ficha_id es NULLABLE y el NULL significa DOS cosas distintas, separadas
-- por la fecha de corte (31/08/2026), igual que en reprocesos.ficha_id:
--   antes del corte  = conteo viejo, "todo el artículo junto". No se
--                      completa: nadie va a poder reconstruir a ojo cómo
--                      se repartía aquel número.
--   después del corte = los BULTOS SUELTOS del artículo, sin procesar.
--                       Es un conteo válido y completo, no un pendiente.
--
-- Es la misma partición que ya usa la pantalla del stock inicial: sueltos
-- por artículo, cajas por ficha.
--
-- ADITIVA: no modifica ninguna fila existente ni rompe el código
-- desplegado (nada lee todavía la columna, y los conteos que se carguen
-- antes de que salga el código nuevo entran con NULL, que es lo que
-- significan).
-- ============================================================================

begin;

-- ---------------------------------------------------------------------------
-- 1. La columna.
--    SIN "on delete set null" a propósito, igual que reprocesos.ficha_id y
--    al revés que pedidos_renglones.ficha_id: acá el NULL ya tiene
--    significado propio ("los sueltos"), así que nulear en silencio al
--    borrar una ficha convertiría un conteo de cajas en un conteo de
--    cajones sueltos. El Cotejo mostraría una diferencia inexplicable en
--    los dos lados a la vez.
-- ---------------------------------------------------------------------------
alter table conteos_stock
    add column ficha_id bigint references fichas_logistica (id);

comment on column conteos_stock.ficha_id is
    'De qué ficha son las cajas que se contaron. NULL tiene dos significados que separa la fecha de corte (31/08/2026): antes del corte = conteo viejo, todo el artículo junto, no se completa; después = los BULTOS SUELTOS del artículo, un conteo válido y completo. La ficha tiene que ser del mismo artículo del conteo: eso lo controla el código, como en asignar_ficha_a_reproceso.';

-- ---------------------------------------------------------------------------
-- 2. El índice del Cotejo.
--    conteos_stock no tenía ningún índice más que la primary key. El
--    Cotejo hace DISTINCT ON (articulo_id, ficha_id) ORDER BY
--    articulo_id, ficha_id, creado_en DESC — que es exactamente este
--    orden, así que sale del índice sin ordenar la tabla entera. Con el
--    conteo partido por ficha, esa tabla pasa a crecer por ficha y no por
--    artículo.
-- ---------------------------------------------------------------------------
create index conteos_stock_cotejo_idx
    on conteos_stock (articulo_id, ficha_id, creado_en desc);

commit;
