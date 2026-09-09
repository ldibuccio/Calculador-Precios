-- BLOQUE 2 — LA LISTA DE MOTIVOS. Es la única parte que hay que revisar
-- antes de correr: los valores son una PROPUESTA mía, no salen de ningún
-- lado del sistema (hoy la merma normal es texto libre, con "Ej: podrido,
-- se rompió el cajón" de placeholder y nada más).
--
-- Cambiar la lista después es otra migración, así que conviene mirarla
-- ahora. Editá los valores de acá abajo si falta o sobra alguno.
--
-- Va en la BASE y no en el código porque es la base la que rechaza: el
-- selector de la pantalla lee de acá (mismo criterio que los siete
-- orígenes de reprocesos_consumos, que tienen un test parseando el CHECK
-- del esquema para que la pantalla y la base no se separen).
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'remitos_segunda_motivo_de_la_lista'
    ) then
        alter table remitos_segunda
            add constraint remitos_segunda_motivo_de_la_lista
            check (motivo is null or motivo in (
                'podrido',
                'deshidratado',
                'golpeado',
                'plaga',
                'no se llego a remitir'
            ));
    end if;
end $$;
