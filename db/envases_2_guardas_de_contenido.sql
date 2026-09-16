do $$
begin
  alter table envases drop constraint if exists envases_umbral_no_negativo;
  alter table envases add constraint envases_umbral_no_negativo
    check (umbral_reposicion is null or umbral_reposicion >= 0);

  alter table movimientos_envase drop constraint if exists movimientos_envase_origen_check;
  alter table movimientos_envase add constraint movimientos_envase_origen_check
    check (origen in ('conteo_inicial', 'compra', 'prestamo_salida', 'ajuste'));

  alter table movimientos_envase drop constraint if exists movimientos_envase_signo_segun_origen;
  alter table movimientos_envase add constraint movimientos_envase_signo_segun_origen
    check (case origen
             when 'compra'          then cantidad > 0
             when 'prestamo_salida' then cantidad < 0
             when 'conteo_inicial'  then cantidad >= 0
             else cantidad <> 0
           end);

  alter table movimientos_envase drop constraint if exists movimientos_envase_ajuste_con_motivo;
  alter table movimientos_envase add constraint movimientos_envase_ajuste_con_motivo
    check (origen <> 'ajuste' or btrim(coalesce(motivo, '')) <> '');

  if (select count(*) from pg_constraint
       where conname in ('envases_umbral_no_negativo',
                         'movimientos_envase_origen_check',
                         'movimientos_envase_signo_segun_origen',
                         'movimientos_envase_ajuste_con_motivo')) <> 4 then
    raise exception 'quedaron menos de 4 guardas de contenido: el bloque no se aplico entero';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 2 de 5. CORRE SOLO. Verificacion aparte (envases_6).
--
-- TODO ESTE BLOQUE ES CONTENIDO —una lista de origenes, los signos, un
-- umbral— asi que va con `drop constraint if exists` y recrear, NUNCA con
-- `if not exists`. Con la guarda de idempotencia, corregir la lista y
-- volver a correr sale `DO` y no hace nada: el constraint ya existe, con la
-- lista vieja adentro, y la pantalla se ve igual que si hubiera funcionado.
--
-- El signo va por origen y no suelto: una compra que reste o un prestamo
-- que sume son la misma fila con el signo al reves, y sin esto entran sin
-- que nada avise.
--
-- `conteo_inicial` admite CERO —contar y que no haya ninguna es un
-- resultado— y por eso el `<> 0` no es global.
