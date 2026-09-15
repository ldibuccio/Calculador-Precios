-- Un artículo que se COMPRA por unidad y se le VENDE por kilo a un cliente
-- necesita saber cuánto pesa una unidad. Eso es lo único que falta: el
-- resto ya está.
--
-- POR QUÉ VA EN EL ARTÍCULO Y NO EN LA COMPRA: lo que varía compra a compra
-- es el FORMATO DE LA CAJA (el mango viene de 40, de 12 y de 10 unidades) y
-- eso YA se guarda por compra, en contenido_por_cajon. Lo que no varía es
-- cuánto pesa UNA unidad — un mango pesa lo que pesa un mango. Cada dato
-- queda donde de verdad cambia, y el comprador no tiene que pesar Y contar
-- cada cajón.
--
-- Y por ser del artículo sale afuera del promedio ponderado del costeo:
-- convertir el contenido de cada compra y convertir el resultado dan
-- EXACTAMENTE lo mismo (verificado con tres formatos). Con un factor por
-- compra eso no vale.
--
-- NULO = NO SE SABE, y ésa es la respuesta correcta para lo que no tiene un
-- valor estable: una CUBETA es un recipiente y cuánto entra depende de cómo
-- se llene. Sin factor el sistema no inventa — se niega a costear esa ficha
-- y lo dice, que es lo que ya hace desde el 15/09.
--
-- ESTRUCTURA, así que el `if not exists` protege de verdad: la columna
-- existe o no, y si existe es la misma (no es una lista de valores).
do $$
begin
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'articulos' and column_name = 'kilos_por_unidad'
    ) then
        alter table articulos add column kilos_por_unidad numeric;
        alter table articulos add constraint articulos_kilos_por_unidad_check
            check (kilos_por_unidad is null or kilos_por_unidad > 0);
    end if;
end $$;

comment on column articulos.kilos_por_unidad is
    'Cuanto pesa UNA unidad de este articulo, en kilos (ej. Mango: 0.4). Convierte entre unidad y kilo en las dos direcciones, para costear una ficha que se vende en otra unidad que la de compra. NULO = no se sabe: ahi el sistema NO costea esa ficha en vez de inventar un numero. No aplica a cubeta, que no tiene un peso estable.';
