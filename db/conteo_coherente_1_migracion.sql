-- COHERENCIA DEL CONTEO.
--
-- ESTE BLOQUE SE CORRE SOLO. La verificación va en una corrida APARTE
-- (`conteo_coherente_2_verificacion.sql`): pegados juntos, el editor corre la
-- última y EL `do` NO SE EJECUTA — sin un solo error, y devolviendo "no rows",
-- que es su salida normal. Pasó el 15/09 y dejó el check en una base y no en
-- la otra.
--
-- Y el código va ARRIBA con la explicación al pie, por lo mismo del otro lado:
-- con los comentarios adelante, un corte del editor deja un archivo que es
-- puro comentario, corre bien y no hace nada.
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
            'Corregilos antes del check: correr db/referencia_2_cuales_son.sql.',
            v_ofensores;
    end if;

    alter table articulos drop constraint if exists articulos_conteo_coherente;

    alter table articulos add constraint articulos_conteo_coherente check (
        coalesce(unidad_compra, 'kilo') = 'kilo'
        or unidad_conteo is null
        or unidad_conteo = unidad_compra
    );
end $$;

-- POR QUÉ ESTÁ ESCRITO ASÍ (al pie para que ningún corte se coma el código):
--
-- Qué impide: `unidad_compra` dice en qué unidad está expresado
-- `compras.contenido_por_cajon` de ese artículo. Con `unidad_conteo` en OTRA,
-- una ficha que venda en esa otra unidad costearía contra un número que está
-- en la primera: cuarenta UNIDADES leídas como cuarenta CUBETAS. No se
-- descuadra nada y el costo sale mal.
--
-- La guarda ya está en Python (`_negar_si_el_conteo_contradice_la_unidad_de_compra`,
-- app/db.py). Esto la pone donde DECIDE: un UPDATE desde el editor no pasa por
-- ahí, y una regla que vive en un solo lado se separa.
--
-- `drop if exists` + recrear y NO `if not exists`: adentro hay literales, o sea
-- CONTENIDO, y ahí la idempotencia esconde en vez de proteger.
--
-- Todo en UN `do` porque el editor no sostiene transacciones: la guarda tiene
-- que abortar antes de que el drop deje la tabla sin constraint.
--
-- APLICADO Y VERIFICADO EN LAS DOS EL 15/09: guarda 1 · ofensores 0 · contados 4.
