do $$
begin
  alter table cargas_compra add column if not exists dias integer;
  update cargas_compra set dias = 1 where dias is null;
  alter table cargas_compra drop constraint if exists cargas_compra_dias_check;
  alter table cargas_compra add constraint cargas_compra_dias_check
    check (dias is null or dias >= 1);
  comment on column cargas_compra.dias is 'PARA CUANTOS DIAS es la compra (dueno, 23/09): multiplica el promedio diario. Igual que el margen, SOLO sobre lo que el promedio propone: lo corregido y lo de a mano ya es lo que se compra. Las cargas anteriores quedaron en 1 porque se cargaron para un dia.';
end $$;

-- ITEM 4 del 23/09. EXPAND (corolario 94): nullable, así el código que
-- está desplegado hoy —que no la nombra— sigue insertando. El NOT NULL va
-- en cargas_compra_dias_2.sql, DESPUÉS del deploy. Verificación APARTE.
