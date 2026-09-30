do $$
begin
  if to_regclass('fotos_borradas_por_antiguedad') is not null then
    raise exception 'fotos_borradas_por_antiguedad ya existe: este bloque ya corrio';
  end if;
  create table fotos_borradas_por_antiguedad (
    foto_ruta text primary key,
    tipo text not null,
    subida_el timestamptz not null,
    bytes bigint,
    borrada_el timestamptz not null default now()
  );
  comment on table fotos_borradas_por_antiguedad is
    'REGISTRO de las fotos cuyo ARCHIVO se borro por tener mas de 3 anios '
    '(duenio, 30/09). La fila que la nombraba NO se toca: "Ver foto" muestra '
    '"Foto borrada por antiguedad el DD/MM/AAAA".';
end $$;

-- FOTOS (duenio, 30/09), bloque 4 de 4: el registro de las borradas.
--
-- Reemplaza a la limpieza de Sistema, que no pedia clave, BORRABA la fila
-- y contaba la antiguedad por la fecha de la compra. Ahora la hace Gerencia
-- -> "Fotos de mas de 3 anios", a mano y con confirmacion; la edad se cuenta
-- desde que se subio cada foto, y lo que queda es esta fila.
--
-- tipo es texto libre a proposito: dice de donde era la foto (pesada,
-- comanda, vale...) para mostrarlo, y no decide nada.
