-- Rediseño del módulo de compras: proveedor estructurado (codigo_puesto +
-- nombre) y renglones de compra con cajones/contenido guardados en crudo.
--
-- Este script BORRA los datos de prueba de compras y proveedores para
-- arrancar limpio con el modelo nuevo. No está pensado para correrlo dos
-- veces (no es idempotente como los otros archivos de db/, justamente
-- porque borra datos). Correr una sola vez, a mano, en el editor SQL de
-- Supabase.

begin;

-- Si esto falla por una FK de recepciones/aprendizaje_proveedores/
-- aprendizaje_articulos, es porque ya hay datos cargados ahí: avisame y lo
-- resolvemos aparte antes de seguir.
delete from compras;
delete from proveedores;

-- proveedores: nave+puesto (nunca se usaron con datos reales) se
-- reemplazan por un único codigo_puesto, con el formato validado también
-- en la base como red de seguridad (letra N o L + 2 dígitos + P + 2
-- dígitos, ej. N07P41, L03P38).
alter table proveedores drop constraint if exists proveedores_nave_puesto_key;
alter table proveedores drop column if exists nave;
alter table proveedores drop column if exists puesto;
alter table proveedores add column codigo_puesto text unique not null
    check (codigo_puesto ~ '^[NL][0-9]{2}P[0-9]{2}$');

comment on table proveedores is 'Proveedores del mercado. La identidad estable es codigo_puesto (ej. N07P41); el nombre es editable, la última corrección manda.';

-- compras: además del total ya calculado (cantidad_kilos/cantidad_fraccion,
-- que sigue usando el motor de costeo tal cual), ahora se guarda también
-- lo que tipeó el comprador (cajones × contenido por cajón), para que la
-- lista se vea como la comanda real y no como un dato ya procesado.
alter table compras add column cantidad_cajones numeric not null;
alter table compras add column contenido_por_cajon numeric not null;

commit;
