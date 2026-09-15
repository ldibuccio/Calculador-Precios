-- EL CONTEO NO PUEDE CONTRADECIR LA UNIDAD EN QUE ESTÁ ESCRITA LA HISTORIA.
--
-- `unidad_compra` dice en qué unidad está expresado `compras.contenido_por_cajon`
-- de ese artículo. Si `unidad_conteo` declarara OTRA, una ficha que venda en esa
-- otra unidad costearía contra un número que está en la primera: cuarenta
-- UNIDADES leídas como cuarenta CUBETAS. No se descuadra nada y el costo sale mal.
--
-- La guarda ya está en Python (`_negar_si_el_conteo_contradice_la_unidad_de_compra`,
-- app/db.py). Esto la pone donde DECIDE: un UPDATE a mano desde el editor no
-- pasa por app/db.py, y una regla que vive en un solo lado se separa.
--
-- CONTENIDO, NO ESTRUCTURA: adentro del check hay literales ('kilo'), así que
-- va `drop if exists` + recrear y NO un `if not exists` — uno idempotente sobre
-- contenido no hace nada y se ve igual que uno que corrió bien.
--
-- PENDIENTE AL CONFIRMAR, y va acá y no en un mensaje porque el que abre este
-- archivo es el que la va a correr: cuando esto salga bien en las DOS bases,
-- el mismo commit tiene que (a) meter el check en `db/esquema_completo.sql`
-- —una migración que cambia un COMPORTAMIENTO no agrega ninguna columna, así
-- que el test de columnas no la ve (corolario 60)— y (b) atar la guarda de
-- Python a este texto con un test, para que las dos no se separen.
--
-- Todo en UN `do`: el editor no sostiene transacciones, y la guarda de ofensores
-- tiene que abortar antes de que el drop deje la tabla sin constraint.
do $$
declare
    v_ofensores integer;
begin
    select count(*) into v_ofensores
    from articulos
    where coalesce(unidad_compra, 'kilo') <> 'kilo'
      and unidad_conteo is not null
      and unidad_conteo <> unidad_compra;

    if v_ofensores > 0 then
        raise exception
            'Hay % articulo(s) con el conteo contradiciendo su unidad de compra. '
            'Corregilos antes de poner el check: correr db/referencia_2_cuales_son.sql.',
            v_ofensores;
    end if;

    alter table articulos drop constraint if exists articulos_conteo_coherente;

    alter table articulos add constraint articulos_conteo_coherente check (
        coalesce(unidad_compra, 'kilo') = 'kilo'
        or unidad_conteo is null
        or unidad_conteo = unidad_compra
    );
end $$;
