-- Agrega merma_porcentaje a articulos. Se habia perdido al consolidar la
-- migracion de clientes en migracion_clientes_final.sql. Seguro de correr
-- aunque la columna ya exista (if not exists).

alter table articulos add column if not exists merma_porcentaje numeric not null default 0;

comment on column articulos.merma_porcentaje is 'Porcentaje de merma esperado del articulo (0 = sin merma).';
