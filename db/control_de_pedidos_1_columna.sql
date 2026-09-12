-- CONTROL DE PEDIDOS (bloque 1 de 2): la columna y su guarda.
--
-- QUÉ AGREGA: el tilde de "Administración controló este renglón", en la
-- misma pantalla de Buscar Pedidos. Guarda CUÁNDO y nada más: el sistema
-- no tiene usuarios —el acceso es por clave de zona y por dispositivo, y
-- el esquema ya dice que la tabla de operarios se borró a propósito— así
-- que un "quién" sería un campo sin consecuencia, de los que se llenan
-- vacíos.
--
-- EL ESTADO DEL PEDIDO NO SE GUARDA: "controlado" es una CUENTA (todos sus
-- renglones vigentes y armados tienen tilde), no una columna. Así un
-- renglón nuevo lo vuelve incompleto solo, sin que nadie tenga que
-- acordarse de destildar nada.
--
-- LA GUARDA ES LA REGLA, y por eso vive acá y no en el código: un renglón
-- controlado y sin armar no puede existir. Lo que se controló fue ESTE
-- renglón con estos bultos y estos kilos; si se desarma, esos números
-- dejaron de existir y el tilde estaría afirmando algo sobre otra cosa.
-- Con el CHECK puesto, el UPDATE que desarma FALLA si no limpia el tilde
-- en la misma sentencia — decide la base, el código traduce el error.
--
-- Y el caso ESPEJO, preguntado a propósito: armado SIN controlar es el
-- estado normal y tiene que seguir entrando. La guarda va en una sola
-- dirección.
do $$
begin
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'pedidos_renglones' and column_name = 'controlado_el'
    ) then
        alter table pedidos_renglones add column controlado_el timestamptz;
    end if;

    -- Se borra y se recrea: el `if not exists` sobre un CHECK esconde una
    -- versión vieja de la regla y sale `DO` igual, sin decir nada.
    alter table pedidos_renglones
        drop constraint if exists pedidos_renglones_controlado_solo_armado;
    alter table pedidos_renglones
        add constraint pedidos_renglones_controlado_solo_armado
        check (controlado_el is null or armado_el is not null);
end $$;
