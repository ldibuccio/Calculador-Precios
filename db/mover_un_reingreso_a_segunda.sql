-- Mover UN reingreso de stock vendible a SEGUNDA.
-- LEER ANTES DE CORRERLO: para corregir el destino de un reingreso NO hace
-- falta SQL. El camino por pantalla existe y es mejor:
--   1. Administración → Movimientos de Stock → Anular, en ese reingreso.
--   2. Depósito → Stock → Reingreso, mismo renglón, destino correcto. El
--      tope "ya devuelto" cuenta solo los NO anulados, así que los bultos
--      se liberan y la carga vuelve a entrar.
-- Es lo que dice el comentario de movimientos_stock.pedido_renglon_id:
-- "corregir = anular y recargar", y deja RASTRO —la anulada queda— donde
-- este script pisa la fila y borra que estuvo en stock.
--
-- Queda para cuando ese camino no esté (el renglón ya no se alcanza).
--
-- Caso 09/09 Frutamax: el reingreso 97 (Limón, 07/09, 10 bultos) se cargó
-- 'stock' y eran 10 cajas de SEGUNDA. Otro caso: cambiar el id y los tres
-- valores esperados de la guarda.
do $$
declare
    v_cantidad numeric;
    v_destino  text;
    v_fecha    date;
    v_anulado  timestamptz;
    v_tipo     text;
begin
    -- SIN AGREGADO: con un count(*) esto nunca sería `not found` y un id
    -- inexistente pasaría de largo sin tocar nada y sin avisar.
    select cantidad, destino_rechazo, fecha_operacion, anulado_el, tipo
      into v_cantidad, v_destino, v_fecha, v_anulado, v_tipo
      from movimientos_stock
     where id = 97;
    if not found then
        raise exception 'No existe el movimiento 97.';
    end if;

    -- LA FILA TIENE QUE SER LA QUE CREEMOS: con el id solo, si la base no
    -- es la que pensamos el update cae sobre otra cosa y sin error.
    if v_tipo <> 'reingreso_rechazo' or v_anulado is not null
       or v_cantidad <> 10 or v_fecha <> date '2026-09-07' then
        raise exception 'El 97 no es el esperado: tipo %, cantidad %, fecha %, anulado %.',
            v_tipo, v_cantidad, v_fecha, v_anulado;
    end if;

    -- Si ya se movió, ABORTA: correrlo dos veces tiene que decirlo, no
    -- verse igual que la primera.
    if v_destino is distinct from 'stock' then
        raise exception 'El 97 ya tiene destino % — no se toca.',
            coalesce(v_destino, 'NULL (= stock)');
    end if;

    -- bultos_segunda NO es opcional: lo exige el CHECK
    -- movimientos_stock_segunda_segun_destino, y en segunda es la cantidad
    -- devuelta (misma caja).
    update movimientos_stock
       set destino_rechazo = 'segunda',
           bultos_segunda  = v_cantidad
     where id = 97;
end $$;
