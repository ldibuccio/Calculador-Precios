-- clientes_cuit_3 (dueño, 14/10): borra la columna vieja clientes.cuit, ya pasada a clientes_cuits.
-- Frena si queda un CUIT sin pasar. Corrida en Frutamax y Palmala el 15/10.
do $$
begin
  if exists (select 1 from information_schema.columns where table_schema = 'public'
             and table_name = 'clientes' and column_name = 'cuit') then
    if exists (select 1 from clientes c
               left join clientes_cuits cc on cc.cliente_id = c.id and cc.cuit = c.cuit
               where c.cuit is not null and cc.id is null) then
      raise exception 'hay un CUIT en clientes.cuit que no está en clientes_cuits: no se borra';
    end if;
    alter table clientes drop column cuit;
  end if;
end $$;
