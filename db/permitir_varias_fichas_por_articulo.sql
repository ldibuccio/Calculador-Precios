-- ============================================================================
-- DOS FICHAS DEL MISMO ARTÍCULO PARA UN CLIENTE (Parte 3 de 3, decisión del 26/08)
-- ============================================================================
-- La última de las tres. Acá se cae la pared: hoy fichas_logistica tiene
-- unique (articulo_id, cliente_id), y por eso al dar de alta "Banana
-- Ecuador" para Día, Banana ya no aparece en la lista de artículos — se la
-- tomó "Banana Bolivia".
--
-- EL ORDEN ERA OBLIGATORIO y ya está cumplido:
--   1. (hecha) el precio cuelga de la ficha  — si no, las dos fichas
--      compartirían un solo precio.
--   2. (hecha) el renglón del pedido guarda su ficha — si no, los dos
--      renglones quedarían idénticos en la base y nada río abajo podría
--      distinguirlos.
--   3. (esta) recién ahora, el drop del unique.
--
-- Los backfills de las Partes 1 y 2 fueron exactos PORQUE este unique
-- garantizaba una sola ficha por artículo y cliente. Sacándolo antes,
-- habrían dejado de ser deterministas. Por eso va último.
--
-- LO QUE NO CAMBIA: articulo_id sigue siendo la clave de COMPRA. Banana
-- Bolivia y Banana Ecuador descuentan del MISMO stock de Banana, porque se
-- compró una sola banana. Lo que se separa es la venta: nombre, kilaje,
-- envase y precio.
--
-- ADITIVO Y REVERSIBLE: no borra ni modifica ninguna fila. Si algo sale
-- mal, se vuelve a crear el unique (mientras no se haya cargado la segunda
-- ficha, que es justo lo que habilita esto).
--
-- Va todo en UNA transacción a propósito: el paso 3 puede fallar si hay
-- códigos repetidos (ver la verificación previa, abajo), y no quiero que
-- quede el unique dropeado sin su reemplazo puesto. O entra todo, o no
-- entra nada.
--
-- Correr en las DOS bases (Frutamax y Palmala) y marcar en APLICADO.md. El
-- código que usa esto se mergea recién después de la confirmación.
-- ============================================================================

-- ============================================================================
-- ANTES DE CORRER: verificación previa (esta sí, corrandola sola primero)
-- ============================================================================
-- El paso 3 crea un unique sobre el CÓDIGO del cliente. Si ya hay dos
-- fichas del mismo cliente con el mismo código, la migración entera falla
-- (y no entra nada, que es lo que se quiere). Esto tiene que devolver CERO
-- filas en las dos bases. Si devuelve algo, avisame ANTES de seguir: hay
-- que decidir qué código lleva cada una.
--
-- select cliente_id, lower(trim(codigo_cliente)) as codigo, count(*), array_agg(id) as fichas
--   from fichas_logistica
--  where codigo_cliente is not null and trim(codigo_cliente) <> ''
--  group by 1, 2
-- having count(*) > 1;
-- ============================================================================

begin;

-- 1. La pared. El nombre es el que le puso Postgres solo al crear la tabla
-- (unique inline en el create table), así que es el mismo en las dos bases
-- — igual conviene confirmarlo con el \d de la verificación de abajo.
alter table fichas_logistica
    drop constraint fichas_logistica_articulo_id_cliente_id_key;

-- 2. El unique traía su índice de regalo, y lo estaba usando todo lo que
-- busca "la ficha de este cliente para este artículo" (las ayudas de
-- kilaje, el alias, las pantallas de precios). Al dropearlo se iba también
-- el índice: se repone como índice común, sin la restricción. El orden va
-- invertido a propósito (cliente primero): así el mismo índice sirve para
-- "todas las fichas de este cliente", que es la consulta más frecuente.
create index fichas_logistica_cliente_articulo_idx
    on fichas_logistica (cliente_id, articulo_id);

-- 3. El código del cliente pasa a ser LA clave que desambigua.
--
-- Esta es la contracara del paso 1, y es lo que hace que sacar la pared sea
-- seguro: mientras había una sola ficha por artículo, el código repetido
-- era un problema teórico. Ahora no: el pedido de Día llega con un código
-- por renglón, y el sistema busca la ficha por ese código. Dos fichas del
-- mismo cliente con el mismo código = el sistema elige una de las dos EN
-- SILENCIO, y el que arma se entera cuando la caja ya salió mal.
--
-- Va normalizado (lower + trim) porque el matcheo del código también
-- normaliza: " 90200 " y "90200" son el mismo código para el sistema, y
-- tienen que serlo también para la base. Las fichas sin código quedan
-- afuera del índice (where): no tener código es normal — se matchea por
-- nombre — y muchas fichas sin código no se pisan entre sí.
create unique index fichas_logistica_codigo_cliente_unico
    on fichas_logistica (cliente_id, lower(trim(codigo_cliente)))
    where codigo_cliente is not null and trim(codigo_cliente) <> '';

comment on index fichas_logistica_codigo_cliente_unico is
    'Dos fichas del mismo cliente no pueden compartir el código: desde que un cliente puede tener varias fichas del mismo artículo, el código es lo que decide a cuál de ellas va el renglón del pedido. Repetido, el sistema elegiría una en silencio.';

commit;

-- ============================================================================
-- Verificación (después de correr)
-- ============================================================================
-- 1. El unique viejo NO tiene que estar, y los dos índices nuevos SÍ.
--    En el \d de la tabla: ya no aparece
--    "fichas_logistica_articulo_id_cliente_id_key UNIQUE CONSTRAINT",
--    y sí aparecen fichas_logistica_cliente_articulo_idx y
--    fichas_logistica_codigo_cliente_unico.
--
-- \d fichas_logistica
--
-- 2. La prueba de fuego, que se puede hacer sin tocar nada: esto tiene que
--    dar 0 (ya no hay pared).
--
-- select count(*) as fichas_repetidas_permitidas_ahora
--   from (select cliente_id, articulo_id from fichas_logistica
--          group by 1, 2 having count(*) > 1) x;
--
--    (Da 0 hoy porque todavía no cargaste la segunda ficha — el punto es
--    que ahora PUEDE dar más de 0 sin que la base se queje.)
-- ============================================================================
