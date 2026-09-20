do $$
begin
    alter table movimientos_stock drop constraint if exists movimientos_stock_lote_dirigido_solo_merma;
    alter table movimientos_stock add constraint movimientos_stock_lote_dirigido_solo_merma
        check (tipo in ('merma', 'pase_a_segunda')
               or (lote_tipo is null and lote_origen_id is null));

    alter table movimientos_stock drop constraint if exists movimientos_stock_pase_uno_a_uno;
    alter table movimientos_stock add constraint movimientos_stock_pase_uno_a_uno
        check (tipo <> 'pase_a_segunda' or bultos_segunda = -cantidad);
end $$;

-- BLOQUE 2 de 2. Corre DESPUES del bloque 1 y por separado.
--
-- EL LOTE DIRIGIDO va porque el pase se costea EXACTAMENTE COMO LA MERMA: la
-- plata se pierde, y cual lote la perdio se elige igual que ahi. Sin esto, el
-- pase no podria dirigirse y la merma si, que serian dos reglas para la misma
-- decision.
--
-- EL UNO A UNO es del dueno, del 20/09: diez cajones que salen de primera son
-- diez bultos que entran al pool de segunda. El cajon pasa ENTERO, no se
-- reenvasa — es la misma mercaderia que cambio de categoria. En el reproceso
-- NO es asi (un cajon de 16 da tres cajas de 6), asi que esto no se deduce de
-- alla: se pregunto y se escribe donde se escribe.
--
-- Y NO HACE FALTA UN CHECK DE "cantidad < 0" para el pase, aunque se
-- extrania: `bultos_segunda > 0` ya existe y esta guarda dice
-- `bultos_segunda = -cantidad`, asi que la cantidad negativa sale de las dos
-- juntas. Queda dicho para que nadie agregue el tercero creyendo que falta.
