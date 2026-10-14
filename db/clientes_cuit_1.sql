-- CARTERA DE CHEQUES, listados grandes (dueño, 14/10): el CUIT del cliente, para
-- que el listado de cheques le asigne solo los cheques que él firma.
alter table clientes add column if not exists cuit text
  constraint clientes_cuit_check check (cuit is null or cuit ~ '^[0-9]{11}$');
