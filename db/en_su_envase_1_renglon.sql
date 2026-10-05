do $$
begin
  if exists (select 1 from information_schema.columns
             where table_name = 'pedidos_renglones' and column_name = 'en_su_envase') then
    raise exception 'en_su_envase_1 ya corrio';
  end if;
  -- false = como siempre: sale como dice la ficha (con envase, en caja).
  alter table pedidos_renglones add column en_su_envase boolean not null default false;
  alter table pedidos_renglones add constraint pedidos_renglones_en_su_envase_solo_armado
    check (not en_su_envase or armado_el is not null);
  comment on column pedidos_renglones.en_su_envase is 'Mango, Cherry (ficha con envase_variable): true = salio en el envase en que vino y no gasto cajas de la ficha; false = como dice la ficha. Se elige al armar.';
end $$;

-- EN SU ENVASE O REPROCESADO A CAJA (dueño, 05/10): en las fichas con
-- envase variable, el que arma elige por renglon. En su envase no consume
-- cajas de Dia: sale de los cajones, como una ficha sin envase. Lo armado
-- hasta hoy queda en false (consumio cajas, con sus guias R). Si se corre
-- dos veces, da error y no escribe nada. Verificacion APARTE:
-- en_su_envase_1_verificacion.sql.
