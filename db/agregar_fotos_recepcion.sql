-- Foto de la BALANZA al recepcionar: una por artículo comprado.
-- Correr en las DOS bases ANTES de mergear el código que la usa.
--
-- Aditivo puro: crea una tabla vacía y no toca ninguna existente. Se puede
-- correr con el código viejo andando — nadie la escribe todavía.
--
-- Por qué tabla propia y no un tipo sobre fotos_guia: fotos_guia cuelga de
-- la GUÍA (proveedor + día) y su archivo SE COMPARTE a propósito entre
-- varias guías. Esta cuelga de UNA compra y no se comparte nunca. Mismo
-- patrón que fotos_pedido. Ver docs/foto_de_balanza_al_recepcionar.md.
--
-- La FK va SIN "on delete cascade" a propósito: con cascade el archivo
-- queda huérfano en el bucket y nadie lo va a ir a buscar. El código borra
-- la fila y devuelve la ruta para borrarla del Storage.
--
-- Son DOS bloques. El 1 escribe; el 2 es el que confirma que escribió
-- (un "do" que sale bien NO devuelve filas: la pantalla vacía del editor
-- no dice nada). Correr los dos, en orden, en cada base.

-- ===== BLOQUE 1 — crear la tabla =====
do $$
begin
  if to_regclass('public.compras') is null then
    raise exception 'No existe la tabla compras: esta base no es la del sistema, no se toca nada';
  end if;

  if to_regclass('public.fotos_recepcion') is not null then
    return;  -- ya estaba: no es error, confirmalo con el bloque 2
  end if;

  create table fotos_recepcion (
      id         bigint generated always as identity primary key,
      compra_id  bigint not null references compras (id),
      foto_ruta  text not null,
      creado_en  timestamptz not null default now(),
      unique (compra_id, foto_ruta)
  );

  comment on table fotos_recepcion is
    'Foto de la mercadería sobre la BALANZA al recepcionar, en el bucket "comandas". Una por ARTÍCULO: una fila de compras es un artículo. A diferencia de fotos_guia, el archivo NUNCA se comparte — es el pesaje de esta compra y de ninguna otra —, y por eso al borrar la compra se borra también el archivo del Storage.';

  comment on column fotos_recepcion.foto_ruta is
    'Ruta del archivo en el bucket "comandas". Entra en la limpieza de fotos viejas con el MISMO corte que las comandas (3 años, una sola perilla): ver listar_fotos_para_limpiar en app/db.py.';
end $$;
