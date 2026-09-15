-- SACA kilos_por_unidad. El factor se descartó el 15/09, el mismo día que se
-- agregó: un kilaje por unidad NUNCA es exacto —un mango pesa lo que pesa— y
-- lo que deja es un promedio disfrazado de dato, con números con coma que
-- después no cierran contra nada.
--
-- El modelo que va en su lugar no convierte: la compra declara LAS DOS
-- magnitudes —los kilos, que siempre están, y el conteo cuando corresponda—
-- y la ficha de cada cliente lee la que le toca. Cada ficha usa el número
-- que alguien cargó de verdad.
--
-- SE SACA Y NO SE DEJA "POR SI ACASO": un campo que nadie llena es
-- exactamente lo que este proyecto ya tiene escrito que no se deja. Y no se
-- pierde nada, medido: con_factor 0 en las DOS bases.
--
-- LA GUARDA ES DE CONTENIDO, ASÍ QUE ABORTA EN VEZ DE SALTEAR. Un
-- `if exists` que se saltea se ve igual que uno que corrió. Si alguien
-- alcanzó a cargar un factor entre que se corrió la migración y esto, el
-- bloque FRENA y lo dice: ese número lo escribió una persona y no lo
-- borramos sin avisar.
do $$
declare
    v_con_factor integer;
begin
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'articulos' and column_name = 'kilos_por_unidad'
    ) then
        raise notice 'kilos_por_unidad ya no existe: nada que hacer';
        return;
    end if;

    select count(*) into v_con_factor
      from articulos where kilos_por_unidad is not null;

    if v_con_factor > 0 then
        raise exception
            'HAY % articulo(s) con kilos_por_unidad cargado. No se borra solo: miralos primero (select nombre, kilos_por_unidad from articulos where kilos_por_unidad is not null) y volve a correr esto cuando esten en null.',
            v_con_factor;
    end if;

    alter table articulos drop constraint if exists articulos_kilos_por_unidad_check;
    alter table articulos drop column kilos_por_unidad;
end $$;
