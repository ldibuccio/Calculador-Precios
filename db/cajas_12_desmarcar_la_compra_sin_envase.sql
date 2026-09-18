do $$
declare
  -- EL ID VA UNA SOLA VEZ. Escrito seis veces, un canario con el numero
  -- cambiado abortaba diciendo "la compra 663 no existe" — el mensaje
  -- nombraba una compra que el bloque ya no estaba mirando.
  v_compra constant int := 663;
  v_ficha int;
  v_envase int;
  v_vivas text;
  v_tocadas int;
begin
  select c.ficha_en_origen_id, f.envase_id
    into v_ficha, v_envase
    from compras c
    left join fichas_logistica f on f.id = c.ficha_en_origen_id
   where c.id = v_compra;

  if not found then
    raise exception 'La compra % no existe.', v_compra;
  end if;
  if v_ficha is null then
    raise exception 'La compra % ya no esta marcada: no hay nada que desmarcar.', v_compra;
  end if;
  if v_envase is not null then
    raise exception 'La ficha % SI tiene envase: este bloque es solo para envase perdido.', v_ficha;
  end if;

  select string_agg('R' || id, ', ') into v_vivas
    from reprocesos where compra_origen_id = v_compra and anulado_el is null;
  if v_vivas is not null then
    raise exception 'La compra % todavia tiene la guia % viva. Anulala desde Guias R y volve.',
                    v_compra, v_vivas;
  end if;

  update compras set ficha_en_origen_id = null where id = v_compra;
  get diagnostics v_tocadas = row_count;
  if v_tocadas <> 1 then
    raise exception 'Toco % filas y tenia que tocar 1. No se escribio nada.', v_tocadas;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- DESMARCAR LA COMPRA 663, que quedo diciendo "viene armada en caja nuestra"
-- contra la ficha 21 de Pera, que es de ENVASE PERDIDO.
--
-- Medido con cajas_10 (Frutamax, 18/09): `OTRAS_FICHAS_CON_ENVASE 0` sobre
-- `fichas_del_articulo 1` — ningun cliente recibe Pera en caja nuestra, asi
-- que lo mal cargado es la MARCA y no la ficha.
--
-- LA GUIA R SE ANULA ANTES, DESDE GUIAS R, y este bloque lo EXIGE en vez de
-- hacerlo: esa operacion ya tiene pantalla, y es la misma precondicion que
-- pide `corregir_recepcion_compra`, en el mismo orden.
--
-- Deshacerlo NO MUEVE NINGUN NUMERO. Medido contra el esquema real: el stock
-- da 5.0 antes de la guia, con la guia, anulada y desmarcada. Al anular, el
-- lote `reproceso` desaparece y el cajon vuelve a crudo. Y con las CAJAS YA
-- ARMADAS tampoco: el armado vuelve a tomar del cajon, `sin_lote` en 0.
--
-- El id va hardcodeado UNA sola vez: escrito en cada mensaje, un canario con
-- el numero cambiado abortaba nombrando la compra equivocada.
