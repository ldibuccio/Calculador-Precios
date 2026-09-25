do $$
begin
  alter table guias_compra add column if not exists de_deposito boolean not null default false;

  if not exists (select 1 from pg_constraint where conname = 'guias_compra_dia_proveedor_origen') then
    alter table guias_compra add constraint guias_compra_dia_proveedor_origen
      unique (fecha_operacion, proveedor_id, de_deposito);
  end if;

  comment on column guias_compra.de_deposito is 'true = la guía de los INGRESOS DIRECTOS de Depósito de ese proveedor ese día. Es otra guía que la de Compras: no comparte comanda ni fotos (dueño, 25/09).';
end $$;

-- LA GUÍA PROPIA DEL INGRESO DIRECTO (dueño, 25/09): "el ingreso directo de
-- Depósito nunca es parte de la comanda del Puesto". Hasta hoy la guía es
-- UNA por (día, proveedor); desde el código nuevo son DOS: la de Compras
-- (de_deposito false) y la de Depósito (true).
--
-- ESTE BLOQUE SOLO AGREGA y se corre YA. NO borra el unique viejo: el código
-- que está en producción hace `ON CONFLICT (fecha_operacion, proveedor_id)`,
-- y sin ese unique TODA carga de compra rebotaría hasta el deploy. Mientras
-- convivan los dos, el viejo es el que manda, y es exactamente lo de hoy.
--
-- El unique nuevo es ESTRUCTURA (siempre las mismas tres columnas), así que
-- va con if not exists. Los bloques 2 y 3 se corren DESPUÉS del deploy del
-- código que ya pregunta por el nuevo. Verificación aparte, en el 4.
