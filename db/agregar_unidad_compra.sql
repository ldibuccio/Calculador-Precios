-- Agrega a articulos la unidad en la que se compra cada uno (kilo/unidad/
-- cubeta, siempre la misma) y el contenido de referencia del cajón/caja que
-- se compra (ej. Mango: 10 unidades). Ambas nullable: se completan a mano
-- desde /articulos a medida que haga falta. Sin unidad_compra configurada,
-- el formulario de carga de compras (/compras/nueva) no deja cargar ese
-- artículo, para no adivinar mal la unidad.
--
-- Seguro de correr más de una vez (add column if not exists).

alter table articulos add column if not exists unidad_compra text
    check (unidad_compra in ('kilo', 'unidad', 'cubeta'));
alter table articulos add column if not exists contenido_referencia numeric;

comment on column articulos.unidad_compra is 'Unidad en la que se compra el artículo al proveedor (kilo, unidad o cubeta). Nulo hasta completarlo desde /articulos; sin esto no se puede cargar una compra nueva de ese artículo.';
comment on column articulos.contenido_referencia is 'Cuánto trae habitualmente el cajón/caja que se compra (ej. Mango: 10 unidades). Solo referencia: se puede editar en cada compra si ese día vino distinto.';

-- Borra las compras de prueba cargadas con el formulario viejo (kilos/
-- fracción sueltos), para arrancar limpio con el formato nuevo de cajones.
-- Si esto falla por una FK de recepciones, es porque ya cargaste alguna
-- recepción para una de estas compras: avisame y lo resolvemos aparte.
delete from compras;
