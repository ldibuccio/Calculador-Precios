-- Agrega foto_ruta a compras: la ruta (dentro del bucket privado
-- "comandas" de Supabase Storage) de la foto de la comanda de la que
-- salió ese renglón, para poder mostrarla después desde /compras
-- ("Ver foto").
--
-- Nullable: las compras cargadas antes de este cambio, y las que se
-- cargan a mano (sin foto), no tienen ninguna. Si la subida de la foto al
-- Storage falla al confirmar una compra por foto, la compra se guarda
-- igual con foto_ruta en null — la foto es un extra, nunca bloquea la
-- carga.
--
-- Una comanda = una foto = varios renglones de compra: todos los
-- renglones que salen de la MISMA foto comparten la MISMA foto_ruta. No
-- hay una tabla aparte para la foto, es solo un dato más de cada compra.
--
-- Seguro de correr más de una vez (add column if not exists).

alter table compras add column if not exists foto_ruta text;

comment on column compras.foto_ruta is 'Ruta de la foto de la comanda en el bucket privado "comandas" de Supabase Storage (NULL si la compra se cargó sin foto, o si la subida falló). Los renglones de una misma comanda comparten la misma ruta.';
