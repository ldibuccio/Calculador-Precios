-- Renombra los valores de compras.tipo_retiro: Granel -> Carro, Propia -> Pases.
--
-- Esta migración documenta lo que ya se corrió a mano en Supabase (drop
-- del constraint viejo, UPDATE de los valores existentes, constraint
-- nuevo con los tres valores, DEFAULT 'Clark') — queda en el repo para
-- que cualquier otra base (ej. un futuro deploy de Palmala, corrido
-- desde cero) llegue al mismo estado sin tener que repetir los pasos a
-- mano.
--
-- Idempotente: el DROP usa IF EXISTS, y los UPDATE con WHERE tipo_retiro
-- = 'Granel'/'Propia' no hacen nada si ya se corrieron antes (esos
-- valores ya no existirían en la tabla).
--
-- compras_tipo_retiro_check es el nombre que Postgres le da por defecto
-- al constraint del check inline original de db/schema.sql
-- (tipo_retiro text not null check (tipo_retiro in ('Clark', 'Granel'))),
-- que nunca se actualizó ahí a pesar de que la app ya permitía "Propia"
-- desde antes de este cambio.

begin;

alter table compras drop constraint if exists compras_tipo_retiro_check;

update compras set tipo_retiro = 'Carro' where tipo_retiro = 'Granel';
update compras set tipo_retiro = 'Pases' where tipo_retiro = 'Propia';

alter table compras add constraint compras_tipo_retiro_check
    check (tipo_retiro in ('Clark', 'Carro', 'Pases'));

alter table compras alter column tipo_retiro set default 'Clark';

commit;
