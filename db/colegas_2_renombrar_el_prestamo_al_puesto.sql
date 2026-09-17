do $$
begin
  alter table movimientos_envase drop constraint if exists movimientos_envase_origen_check;
  alter table movimientos_envase drop constraint if exists movimientos_envase_signo_segun_origen;

  update movimientos_envase set origen = 'prestamo_al_puesto'
   where origen = 'prestamo_salida';

  alter table movimientos_envase add constraint movimientos_envase_origen_check
    check (origen in ('conteo_inicial', 'compra', 'prestamo_al_puesto', 'ajuste'));

  alter table movimientos_envase add constraint movimientos_envase_signo_segun_origen
    check (case origen
             when 'compra'             then cantidad > 0
             when 'prestamo_al_puesto' then cantidad < 0
             when 'conteo_inicial'     then cantidad >= 0
             else cantidad <> 0
           end);

  if exists (select 1 from movimientos_envase where origen = 'prestamo_salida') then
    raise exception 'quedaron filas con el origen viejo';
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Bloque 2 de 3. CORRE SOLO. Verificacion aparte (colegas_4).
--
-- SOLO RENOMBRA. No agrega nada: despues de este bloque el sistema hace
-- exactamente lo mismo que antes, con otra palabra. Los origenes de colega
-- entran en el bloque 3.
--
-- POR QUE: la pantalla ofrece hoy una sola salida —"Le mande cajas vacias al
-- puesto"— y va a ofrecer otra, la del colega. Leidos en la misma lista,
-- `prestamo_salida` y `prestamo_colega` se parecen demasiado, y el que llega
-- segundo se queda sin la palabra. El del puesto dice AL PUESTO y el del
-- colega dice COLEGA: ninguno de los dos se llama `prestamo` a secas.
--
-- NO SON EL MISMO HECHO, y por eso conviven en vez de fusionarse: el puesto
-- es TUYO (tiene sus propios clientes y proveedores, tablas clientes_puesto y
-- proveedores_puesto) y la caja vuelve SOLA con la guia R `en_origen`. Con un
-- colega la vuelta la declara una persona, y hay una cuenta que llevar.
--
-- ES CONTENIDO —una lista de valores permitidos— asi que va con `drop
-- constraint if exists` y recrear. Con `if not exists` el bloque saldria `DO`
-- sin hacer nada y el constraint quedaria con la lista vieja adentro: se ve
-- EXACTAMENTE IGUAL que uno que corrio bien.
--
-- EL DROP VA ANTES DEL UPDATE a proposito: con el CHECK viejo puesto, un
-- update a un valor que no esta en su lista lo rechaza la propia guarda.
