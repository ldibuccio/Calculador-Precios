-- Verificación. UNA consulta con CONTEOS: siempre vuelve una fila, así que
-- el cero se ve. Con una lista de ofensores, "todo bien" y "no corrió" son
-- la misma pantalla vacía.
--
-- Esperado: movido_ok 1, sigue_en_stock 0, incoherentes 0.
-- `ultimo_reingreso` es el testigo de actividad: sin él, una base sin
-- reingresos devuelve todo en cero y el cero se lee como éxito.
select
    (select count(*) from movimientos_stock
      where id = 97 and destino_rechazo = 'segunda'
        and bultos_segunda = 10)                              as movido_ok,
    (select count(*) from movimientos_stock
      where id = 97 and coalesce(destino_rechazo, 'stock') = 'stock')
                                                              as sigue_en_stock,
    -- La coherencia de TODA la tabla, no solo de la fila tocada: destino a
    -- segunda sin bultos, o bultos cargados con destino stock.
    (select count(*) from movimientos_stock
      where tipo = 'reingreso_rechazo' and anulado_el is null
        and ((destino_rechazo in ('segunda', 'reproceso') and bultos_segunda is null)
          or (coalesce(destino_rechazo, 'stock') = 'stock' and bultos_segunda is not null)))
                                                              as incoherentes,
    (select count(*) from movimientos_stock
      where tipo = 'reingreso_rechazo' and anulado_el is null) as reingresos_totales,
    (select max(fecha_operacion) from movimientos_stock
      where tipo = 'reingreso_rechazo' and anulado_el is null) as ultimo_reingreso;
