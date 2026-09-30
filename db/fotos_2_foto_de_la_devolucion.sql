do $$
begin
  if exists (select 1 from information_schema.columns
             where table_name = 'fotos_recepcion' and column_name = 'movimiento_id') then
    raise exception 'fotos_recepcion.movimiento_id ya existe: este bloque ya corrio';
  end if;
  alter table fotos_recepcion
    add column movimiento_id bigint references movimientos_stock (id);
  create index fotos_recepcion_movimiento on fotos_recepcion (movimiento_id);
  -- Las que ya estan: la ruta de una foto de devolucion lleva "devolucion-"
  -- (la arma la ruta de /deposito/devolver). Va a la devolucion de ESA
  -- compra mas cercana en el tiempo.
  update fotos_recepcion f
     set movimiento_id = (
       select m.id from movimientos_stock m
        where m.tipo = 'devolucion_deposito' and m.compra_devolucion_id = f.compra_id
        order by abs(extract(epoch from m.creado_en - f.creado_en)), m.id
        limit 1)
   where f.foto_ruta like '%/devolucion-%';
end $$;

-- FOTOS (duenio, 30/09), bloque 2 de 4: la foto de una DEVOLUCION de
-- mercaderia desde deposito.
--
-- Esas fotos van a fotos_recepcion, las mismas de la compra, y el boton
-- "borrar foto de pesada" del detalle de la compra las borraba igual que una
-- pesada subida por error. Con movimiento_id puesto, la foto es de la
-- devolucion: el detalle no ofrece borrarla y la escritura la rechaza.
--
-- Es ESTRUCTURA (una columna), asi que la guarda es "ya existe". El update
-- solo toca fotos de devolucion; en Frutamax al 30/09 no habia ninguna.
-- Una foto de devolucion sin devolucion que la nombre queda en NULL y la
-- verificacion la cuenta (devolucion_sin_marcar).
