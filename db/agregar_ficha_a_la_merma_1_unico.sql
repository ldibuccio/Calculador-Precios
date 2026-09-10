-- MERMA POR FICHA (bloque 1 de 3): la clave que la FK compuesta necesita.
--
-- Va PRIMERO y solo: el bloque 2 no puede crear su FK sin esto.
--
-- Por qué una FK COMPUESTA y no la simple de siempre: una merma dice
-- artículo Y ficha, y si la ficha es de OTRO artículo la cuenta por ficha
-- se ensucia en silencio — que es exactamente el modo de falla que este
-- cambio viene a cerrar. Con (ficha_id, articulo_id) apuntando acá, esa
-- fila no entra: decide la base y el código traduce el error.
--
-- `id` ya es primary key, así que este unique es redundante para Postgres
-- y su única razón de existir es habilitar la FK compuesta. Se deja dicho
-- para que nadie lo borre por "sobra".
--
-- ESTRUCTURA, así que el `if not exists` está bien acá: la restricción
-- existe o no, y si existe es la misma (no hay literales adentro).
do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'fichas_logistica_id_articulo_unico'
    ) then
        alter table fichas_logistica
            add constraint fichas_logistica_id_articulo_unico
            unique (id, articulo_id);
    end if;
end $$;
