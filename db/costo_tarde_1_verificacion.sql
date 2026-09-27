select 'costo_tarde_1_completar_lo_que_ya_esta' as QUE_MIGRACION,
  (select count(*) from reprocesos_consumos rc
     join compras c on c.id = rc.compra_id
     join reprocesos r on r.id = rc.reproceso_id
    where r.anulado_el is null and rc.costo_por_bulto is null
      and c.importe is not null) as consumos_compra_por_completar,
  (select count(*) from reprocesos_consumos rc
     join reprocesos o on o.id = rc.origen_id and rc.origen = 'reproceso'
     join reprocesos r on r.id = rc.reproceso_id
    where r.anulado_el is null and rc.costo_por_bulto is null
      and o.costo_por_bulto_primera is not null) as consumos_reproceso_por_completar,
  (select count(*) from reprocesos r
    where r.anulado_el is null and r.costo_total is null
      and exists (select 1 from reprocesos_consumos x where x.reproceso_id = r.id)
      and not exists (select 1 from reprocesos_consumos x
                       where x.reproceso_id = r.id and x.costo_por_bulto is null)) as guias_completas_sin_total,
  (select count(*) from reprocesos
    where anulado_el is null and costo_total is null) as guias_sin_costo_que_quedan,
  (select count(*) from reprocesos where anulado_el is null) as POBLACION_guias,
  (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r;

-- Corrida ANTES del do dice cuánto hay para completar; DESPUÉS, las tres
-- primeras columnas tienen que dar 0. guias_sin_costo_que_quedan son las
-- que esperan un precio que no llegó o que no puede llegar (ajuste,
-- stock inicial, sin lote): esas no las toca esto.
