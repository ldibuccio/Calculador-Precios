-- Permite compras sin precio (frecuente: se compra de noche sin precio, se
-- arregla por teléfono a la mañana). El importe queda vacío hasta que se
-- carga desde /compras/pendientes.
--
-- Seguro de correr más de una vez: si la columna ya admite null, el DROP
-- NOT NULL no hace nada.

alter table compras alter column importe drop not null;

comment on column compras.importe is 'Importe de la compra. Nulo = compra sin precio todavia (se completa despues desde /compras/pendientes). El costeo debe excluir las filas con importe nulo.';
