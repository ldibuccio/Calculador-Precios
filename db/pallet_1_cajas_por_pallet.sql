do $$
begin
  alter table envases add column if not exists cajas_por_pallet integer;
  alter table envases drop constraint if exists envases_cajas_por_pallet_positivo;
  alter table envases add constraint envases_cajas_por_pallet_positivo
    check (cajas_por_pallet is null or cajas_por_pallet > 0);
  comment on column envases.cajas_por_pallet is 'Cuantas cajas de ESTE envase entran en un pallet. Se carga una vez (dueno, 23/09) y la pantalla de Cajas muestra el stock como pallets mas cajas sueltas. NULL = no se cargo: ese envase se sigue mostrando solo en cajas.';
end $$;

-- ITEM 3 del 23/09: cuántas cajas entran en un pallet, por envase.
-- La guarda se DROPEA y se recrea (contenido, no estructura: CLAUDE.md,
-- "un if not exists sobre CONTENIDO es una trampa"). Correr la verificación
-- APARTE: pallet_1_verificacion.sql.
