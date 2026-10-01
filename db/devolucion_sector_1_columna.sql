do $$
begin
  if exists (select 1 from information_schema.columns
              where table_name = 'movimientos_stock' and column_name = 'cargada_desde') then
    raise exception 'la columna cargada_desde ya existe: este bloque ya corrio';
  end if;
  alter table movimientos_stock add column cargada_desde text;
  alter table movimientos_stock add constraint movimientos_stock_cargada_desde_valida
    check (cargada_desde is null or cargada_desde in ('deposito', 'administracion'));
  update movimientos_stock set cargada_desde = 'deposito'
   where tipo = 'devolucion_deposito';
  comment on column movimientos_stock.cargada_desde is
    'Desde que SECTOR se cargo una devolucion desde deposito (duenio, 01/10): '
    'deposito o administracion. Solo la lleva tipo devolucion_deposito. Las '
    'anteriores al 01/10 son todas de deposito: no habia otra puerta.';
end $$;

-- DEVOLVER MERCADERIA DESDE ADMINISTRACION (duenio, 01/10), bloque 1 de 2.
--
-- Se corre ANTES del deploy. Agrega la columna y marca 'deposito' en las
-- devoluciones que ya estaban (hasta hoy la unica puerta era Deposito). No
-- exige todavia que toda devolucion la tenga: el codigo viejo, que sigue
-- desplegado hasta el merge, no la escribe. Eso lo agrega el bloque 2.
