do $mig$
begin
  if not exists (select 1 from information_schema.columns
                  where table_name = 'pedidos_renglones'
                    and column_name = 'cantidad_original') then
    alter table pedidos_renglones add column cantidad_original numeric;
  end if;

  execute $c$comment on column pedidos_renglones.cantidad_original is
    'Con que cantidad NACIO este renglon, si despues alguien la corrigio a mano. NULL = nunca se corrigio y cantidad es la de siempre. Guarda el VALOR y no un timestamp a proposito: la pregunta que aparece el dia que algo no cierra es "la orden de compra dice 5 y el sistema dice 8, por que", y eso lo contesta el numero viejo, no la hora. Se escribe UNA sola vez, en la primera correccion: la segunda ya tiene el original guardado y no lo pisa.'$c$;
end $mig$;
