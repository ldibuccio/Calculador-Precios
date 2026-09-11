-- LA COMPRA QUE YA VIENE ARMADA EN CAJA NUESTRA: la marca nace en la COMPRA.
-- Bloque unico. Correr en las DOS bases, y despues la verificacion.
--
-- QUIEN SABE que ese bulto viene procesado es el COMPRADOR: el fue al puesto,
-- el mando las cajas, el decidio comprarlo armado en vez del cajon. Antes esto
-- vivia en Recepcion y le pedia al operario una decision comercial que no tomo.
--
-- UNA COLUMNA Y NO DOS. Iba a ser una marca booleana MAS la ficha, con un
-- CHECK espejo. Dos campos que tienen que coincidir son la misma regla escrita
-- dos veces, y el CHECK es el parche que los sostiene. Aca no hace falta: sin
-- ficha la marca no sirve —la guia R exige ficha por CHECK— asi que "viene
-- armada" ES "tiene ficha". Mismo idioma que fichas_logistica.envase_id.
--
-- ES ESTRUCTURA (columna e indice): el `if not exists` protege de verdad.
-- Que la ficha sea DEL MISMO ARTICULO es cruce de tablas y no entra en un
-- CHECK: esa guarda va en el codigo, donde se ESCRIBE.
do $$
begin
  if to_regclass('public.compras') is null then
    raise exception 'no existe la tabla compras: base equivocada';
  end if;

  alter table compras
    add column if not exists ficha_en_origen_id bigint references fichas_logistica (id);

  execute 'comment on column compras.ficha_en_origen_id is ' || quote_literal(
    'NO NULO = esta compra viene YA ARMADA en caja nuestra, y esta es la ficha '
    'a la que van esas cajas. La marca el COMPRADOR al cargarla, que es el '
    'unico que lo sabe. Al recepcionar, el sistema genera solo la guia R tipo '
    'en_origen (reprocesos.compra_origen_id apunta de vuelta aca). NULL = '
    'compra normal, llega el cajon del proveedor. El nombre lleva el alcance: '
    'no es la ficha de la compra en general, es la del armado en origen.');

  -- Para que eliminar_ficha enumere las compras que la apuntan sin barrer la
  -- tabla. Parcial porque la enorme mayoria es NULL.
  create index if not exists compras_ficha_en_origen_idx
    on compras (ficha_en_origen_id)
    where ficha_en_origen_id is not null;
end $$;
