select 'segunda_al_cliente_3' as que_migracion,
  (select count(*) from information_schema.columns
    where table_name = 'clientes' and column_name = 'acepta_segunda'
      and is_nullable = 'NO' and column_default = 'false') as tilde,
  (select count(*) from information_schema.columns
    where table_name = 'pedidos_renglones'
      and column_name = 'bultos_de_segunda') as columna,
  (select count(*) from pg_constraint
    where conname = 'pedidos_renglones_segunda_solo_armado'
      and pg_get_constraintdef(oid) like '%armado_el IS NOT NULL%'
      and pg_get_constraintdef(oid) like '%anulado_el IS NULL%') as guarda,
  (select count(*) from clientes where acepta_segunda) as clientes_con_tilde,
  (select count(*) from clientes) as clientes_poblacion,
  (select count(*) from pedidos_renglones
    where bultos_de_segunda is not null) as renglones_con_segunda,
  (select max(armado_el)::date from pedidos_renglones) as testigo_ultimo_armado;

-- Esperado en las dos: tilde 1 · columna 1 · guarda 1 · clientes_con_tilde 0
-- · renglones_con_segunda 0. La poblacion y el testigo dicen de que base es.
