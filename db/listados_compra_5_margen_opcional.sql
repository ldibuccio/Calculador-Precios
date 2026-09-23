do $$
begin
  alter table listados_compra alter column margen_porcentaje drop not null;
end $$;
comment on column listados_compra.margen_porcentaje is 'EN RETIRO (23/09): el margen vive en cargas_compra. Dos que se multiplican son invisibles (20% y 10% son 32%). El codigo nuevo ya no la escribe; se dropea con cargas_compra_3_sacar_las_viejas.sql, DESPUES del deploy.';
comment on column cargas_compra.margen_porcentaje is 'Cuanto se compra de mas para ESTE cliente, en por ciento. SOLO SE APLICA A LO QUE EL PROMEDIO PROPONE (dueno, 23/09): lo corregido y todo lo de a mano ya es lo que se compra y entra tal cual; por eso la pantalla no muestra el campo en modo manual. Es por CARGA y no por listado: dos margenes que se multiplican son invisibles (20% y 10% son 32%). SIN DEFAULT EN LA BASE: el de arranque es MARGEN_SUGERIDO (core/que_comprar.py). 0 es sin margen.';

-- SE CORRE ANTES DEL PUSH del Paso 2, y es lo único que va antes.
--
-- El código nuevo inserta `listados_compra (fecha, estado)` sin margen: el
-- margen se fue del listado porque vive en cada carga. Con el NOT NULL
-- puesto, ese INSERT rebota y "Qué comprar hoy" no puede guardar el primer
-- borrador del día. Sacar el NOT NULL no rompe el código viejo —ése la sigue
-- escribiendo— así que este bloque se puede correr en cualquier momento
-- antes del deploy.
--
-- NO SE DROPEA ACÁ la columna: el código viejo la lee y la escribe hasta que
-- el deploy salga. El drop va con las tablas viejas, en
-- cargas_compra_3_sacar_las_viejas.sql, que se corre DESPUÉS.
--
-- Es ESTRUCTURA y no contenido, así que correrlo dos veces no esconde nada.
--
-- Verificación APARTE: db/listados_compra_5_verificacion.sql.
