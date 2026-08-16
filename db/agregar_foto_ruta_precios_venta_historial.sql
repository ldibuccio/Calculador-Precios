-- Agrega foto_ruta a precios_venta_historial: la ruta (dentro del bucket
-- privado "comandas" de Supabase Storage) del archivo (foto, PDF o Excel)
-- del que salió esa fila de precio, para poder mostrarlo después
-- ("Ver archivo").
--
-- Nullable: las filas cargadas antes de este cambio, y las que se cargan a
-- mano (Carga Manual de Precios, sin archivo), no tienen ninguna. Si la
-- subida del archivo al Storage falla al confirmar una carga por foto, los
-- precios se guardan igual con foto_ruta en null — el archivo es un
-- extra, nunca bloquea la carga.
--
-- Una carga de "Cargar Foto Precios" = un archivo = varias filas de
-- precio (una por artículo leído): todas las filas que salen del MISMO
-- archivo comparten la MISMA foto_ruta.
--
-- Seguro de correr más de una vez (add column if not exists).

alter table precios_venta_historial add column if not exists foto_ruta text;

comment on column precios_venta_historial.foto_ruta is 'Ruta del archivo (foto/PDF/Excel) del que salió este precio, en el bucket privado "comandas" de Supabase Storage (NULL si se cargó a mano, o si la subida falló). Las filas de una misma carga comparten la misma ruta.';
