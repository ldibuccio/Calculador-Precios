do $$
declare
  v_compra bigint := 0;   -- PEGAR ACA el id de la compra (paso 1)
  m record;
  c record;
  n int;
begin
  if v_compra <= 0 then
    raise exception 'Falta poner el id de la compra en v_compra';
  end if;
  select * into m from movimientos_stock where id = 170 for update;
  if not found then raise exception 'No existe el movimiento 170'; end if;
  if m.anulado_el is not null then raise exception '170 esta anulado'; end if;
  if m.destino_rechazo is distinct from 'devolucion_proveedor'
     or m.pedido_renglon_id is distinct from 2277 then
    raise exception '170 no es la devolucion del renglon 2277';
  end if;
  if m.compra_devolucion_id is not null then
    raise exception '170 ya tiene compra: %', m.compra_devolucion_id;
  end if;
  select * into c from compras where id = v_compra;
  if not found then raise exception 'No existe la compra %', v_compra; end if;
  if c.articulo_id <> m.articulo_id then
    raise exception 'La compra % es de otro articulo', v_compra;
  end if;
  if c.proveedor_id is distinct from m.proveedor_devolucion_id then
    raise exception 'La compra % es de otro proveedor', v_compra;
  end if;
  if c.estado <> 'recepcionado' then
    raise exception 'La compra % no esta recepcionada', v_compra;
  end if;
  update movimientos_stock
     set compra_devolucion_id = v_compra, proveedor_devolucion_id = null
   where id = 170 and compra_devolucion_id is null;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'Se tocaron % filas, no 1', n; end if;
end $$;

-- devolucion_valor_2: ata el movimiento 170 (rechazo del 28/09, 10 Mzn
-- Granny, FRUTAMAX S.R.L.) a la compra de la que salio el armado del renglon
-- 2277. Se corre SOLO, sin la verificacion pegada (va en devolucion_valor_3).
-- v_compra arranca en 0 y la guarda pide > 0: un reemplazo global no la
-- puede engañar. El proveedor pasa a leerse de la compra (el CHECK no deja
-- las dos columnas puestas). Si la compra tiene SEÑA y el renglon iba en el
-- cajon, esos 10 cajones salen de Vacios de ese proveedor: es la regla de la
-- devolucion con seña, no un efecto raro.
