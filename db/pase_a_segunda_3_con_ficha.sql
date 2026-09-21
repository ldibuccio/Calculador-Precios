-- pase_a_segunda_3_con_ficha.sql — CORRIDO Y CONFIRMADO en las dos bases el 21/09.
do $$
begin
    alter table movimientos_stock drop constraint if exists movimientos_stock_ficha_solo_merma;
    alter table movimientos_stock drop constraint if exists movimientos_stock_ficha_solo_merma_o_pase;
    alter table movimientos_stock add constraint movimientos_stock_ficha_solo_merma_o_pase
        check (tipo in ('merma', 'pase_a_segunda') or ficha_id is null);
end $$;

-- Deja que el PASE A SEGUNDA diga de que porcion salio, igual que la merma.
--
-- El caso es del dueno (21/09): se armo una caja para Dia, no salio, y se
-- puso fea. Tiene que poder pasar a segunda directo.
--
-- ESTO DA VUELTA LA DECISION DEL 20/09, que esta escrita en el pie de
-- db/pase_a_segunda_1.sql: "el pase sale de los SUELTOS; una caja ya armada
-- que se pone fea no es un pase, es desarmarla primero". Era una deduccion
-- nuestra sobre como se trabaja, no un hecho del galpon, y el dueno la
-- corrigio. Queda anotada aca y no borrada alla: el que lea aquel pie tiene
-- que poder llegar hasta esta linea.
--
-- ES CONTENIDO —una lista de valores— asi que va con `drop` y recrear y NO
-- con `if not exists`: un CHECK que ya existe con la lista vieja se saltearia
-- en silencio y saldria `DO` igual.
--
-- SE DROPEAN LOS DOS NOMBRES, el viejo y el nuevo: el viejo para la primera
-- corrida y el nuevo para la segunda. Sin el segundo `drop`, correrla dos
-- veces falla por duplicado.
--
-- EL NOMBRE CAMBIA porque el viejo pasa a ser falso. Un constraint que se
-- llama `solo_merma` y acepta dos tipos es la clase de nombre que se lee y
-- no se verifica.
--
-- ABRE UNO Y NO TODOS: un ajuste o un reingreso con ficha siguen frenados.
-- El reingreso YA llega a su ficha por el renglon que volvio, y dos caminos
-- al mismo dato es la regla escrita dos veces.
