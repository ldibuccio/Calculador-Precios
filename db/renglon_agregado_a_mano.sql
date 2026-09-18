do $mig$
begin
  if not exists (select 1 from information_schema.columns
                  where table_name = 'pedidos_renglones'
                    and column_name = 'agregado_a_mano_el') then
    alter table pedidos_renglones add column agregado_a_mano_el timestamptz;
  end if;

  execute $c$comment on column pedidos_renglones.agregado_a_mano_el is
    'Cuando se agrego este renglon a mano a un pedido YA CARGADO. NULL = vino en la comanda, que es el caso normal. Existe porque pedidos.origen es del PEDIDO y no del renglon: sin esto un articulo que el super agrego por telefono es indistinguible de uno que vino en el mail, y el dia que algo no cierre contra la orden de compra eso es lo primero que hay que mirar. Guarda CUANDO y nada mas, igual que controlado_el: el sistema no tiene usuarios, asi que un quien seria un campo sin consecuencia.'$c$;
end $mig$;
