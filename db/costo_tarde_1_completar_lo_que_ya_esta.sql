do $$
declare
  vuelta  int := 0;
  tocadas int;
begin
  loop
    vuelta := vuelta + 1;
    if vuelta > 100 then
      raise exception 'la cascada no termina en 100 vueltas: no se escribio nada';
    end if;

    update reprocesos_consumos rc set costo_por_bulto = c.importe
      from compras c, reprocesos r
     where c.id = rc.compra_id and r.id = rc.reproceso_id
       and r.anulado_el is null
       and rc.costo_por_bulto is null and c.importe is not null;

    update reprocesos_consumos rc set costo_por_bulto = o.costo_por_bulto_primera
      from reprocesos o, reprocesos r
     where rc.origen = 'reproceso' and o.id = rc.origen_id
       and r.id = rc.reproceso_id and r.anulado_el is null
       and rc.costo_por_bulto is null and o.costo_por_bulto_primera is not null;

    update reprocesos r
       set costo_total = s.total,
           costo_por_bulto_primera = case when r.bultos_primera > 0
                                          then round(s.total / r.bultos_primera, 2) end
      from (select reproceso_id, round(sum(bultos * costo_por_bulto), 2) as total
              from reprocesos_consumos
             group by reproceso_id
            having count(*) filter (where costo_por_bulto is null) = 0) s
     where s.reproceso_id = r.id
       and r.costo_total is null and r.anulado_el is null;
    get diagnostics tocadas = row_count;
    exit when tocadas = 0;
  end loop;
end $$;

-- COMPLETA EL COSTO DE LAS GUÍAS R QUE QUEDARON ESPERANDO UN IMPORTE (26/09).
--
-- El caso: la compra 776 recibió su importe el 25/09 y las guías R 502 y 527
-- de Palta, que la habían consumido antes, siguieron sin costo. Igual las
-- 141, 144, 150 y 151 del 05/09. Desde este commit el código lo hace solo al
-- cargar el importe; esto arregla lo que ya estaba.
--
-- SOLO LLENA NULL, nunca pisa un costo congelado. Tres pasos por vuelta:
-- los consumos de COMPRA con el importe de hoy, los consumos de REPROCESO
-- (la primera de otra guía R, que entra al FIFO como lote) con el costo de
-- esa guía, y el total de las guías que quedaron sin ningún consumo en NULL.
-- Repite mientras alguna guía se complete: así baja la cascada.
--
-- No usa ids: en Palmala, sin nada que completar, da una vuelta y sale.
-- La verificación va APARTE: costo_tarde_1_verificacion.sql.
