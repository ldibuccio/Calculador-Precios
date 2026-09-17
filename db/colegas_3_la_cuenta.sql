do $$
begin
  alter table movimientos_envase
    add column if not exists colega_id bigint references colegas (id);

  alter table movimientos_envase drop constraint if exists movimientos_envase_origen_check;
  alter table movimientos_envase add constraint movimientos_envase_origen_check
    check (origen in ('conteo_inicial', 'compra', 'prestamo_al_puesto', 'ajuste',
                      'colega_le_presto', 'colega_me_devuelve',
                      'colega_me_presta', 'colega_le_devuelvo'));

  alter table movimientos_envase drop constraint if exists movimientos_envase_signo_segun_origen;
  alter table movimientos_envase add constraint movimientos_envase_signo_segun_origen
    check (case
             when origen = 'conteo_inicial' then cantidad >= 0
             when origen in ('compra', 'colega_me_devuelve', 'colega_me_presta')
               then cantidad > 0
             when origen in ('prestamo_al_puesto', 'colega_le_presto', 'colega_le_devuelvo')
               then cantidad < 0
             else cantidad <> 0
           end);

  alter table movimientos_envase drop constraint if exists movimientos_envase_colega_segun_origen;
  alter table movimientos_envase add constraint movimientos_envase_colega_segun_origen
    check ((colega_id is not null) is not distinct from
           (origen in ('colega_le_presto', 'colega_me_devuelve',
                       'colega_me_presta', 'colega_le_devuelvo')));

  if (select count(*) from pg_constraint
       where conname in ('movimientos_envase_origen_check',
                         'movimientos_envase_signo_segun_origen',
                         'movimientos_envase_colega_segun_origen')) <> 3 then
    raise exception 'faltan guardas: el bloque no se aplico entero';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 3 de 3. CORRE SOLO. Verificacion aparte (colegas_4).
--
-- `cantidad` SIGUE SIENDO EL EFECTO SOBRE EL PISO, y el signo se agrupa por
-- eso: entra o sale. Asi el fisico no gana ninguna pata y la alerta sigue
-- mirando solo el piso sin que nadie tenga que acordarse — una caja que te
-- deben no entra porque no esta en el piso. De ahi el neto sin mapa de
-- signos: neto = -sum(cantidad). El modelo vive en core/envases.py.
--
-- `is not distinct from` y no `=`: un CHECK que evalua NULL PASA (17/09).
-- Y ATA DOS COLUMNAS: la forma del corolario 75. El commit del codigo
-- grepea el INSERT por `origen` Y por `colega_id`, o es una pared.
