-- LA COMPRA QUE YA VIENE ARMADA EN CAJA NUESTRA (guia R tipo 'en_origen').
-- BLOQUE A de 4. Correr A, B, C, D en ese orden (D depende de A), en LAS DOS
-- bases, y despues compra_en_caja_nuestra_2_verificacion.sql.
--
-- El puesto entrega la mercaderia ya reenvasada en NUESTRA caja. Eso paso en
-- origen, no en el galpon: cargar la guia R a mano seria documentar un trabajo
-- que nadie hizo. Al recepcionar se marca que viene armada, se elige la ficha,
-- y el sistema genera la guia R solo.
--
-- POR QUE LA GUIA CONSUME: la compra recepcionada ya sumo +N al stock. Si la
-- guia produjera sin consumir (como las 'inicial' del corte) el articulo
-- quedaria con 2N. Toma N y produce N — neto cero — y lo unico que cambia es
-- que el lote pasa de crudo ('guia') a trabajado ('reproceso'), que es lo que
-- la pared del armado necesita para que esas cajas salgan de su ficha.
--
-- ESTE bloque es ESTRUCTURA (una columna, un indice), asi que el
-- `if not exists` protege de verdad: la columna existe o no, y si existe es
-- la misma. Los bloques B, C y D son CONTENIDO y van con drop y recrear.
do $$
begin
  if to_regclass('public.reprocesos') is null then
    raise exception 'no existe la tabla reprocesos: base equivocada';
  end if;

  alter table reprocesos
    add column if not exists compra_origen_id bigint references compras (id);

  execute 'comment on column reprocesos.compra_origen_id is ' || quote_literal(
    'La compra que llego YA ARMADA en caja nuestra y genero esta guia R sola '
    '(tipo en_origen). NULL en todas las demas. El indice unico de al lado es '
    'lo UNICO que impide que una compra genere dos guias: el freno de stock NO '
    'puede, porque las salidas del mismo dia no cuentan en '
    'reparto_para_reproceso y la segunda guia ve el lote entero (medido).');

  -- Una compra, UNA guia en origen. PARCIAL y no total a proposito: excluye
  -- las anuladas, asi que anular la guia libera la compra para rehacerla —
  -- que es lo que va a querer el que se equivoco de ficha.
  create unique index if not exists reprocesos_una_guia_por_compra
    on reprocesos (compra_origen_id)
    where compra_origen_id is not null and anulado_el is null;
end $$;
