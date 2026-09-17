select
  count(*) filter (where m.envase_id is not null)                as con_envase_ATENCION,
  count(*) filter (where m.destino_rechazo = 'reproceso')         as vuelven_a_cajon,
  count(*) filter (where m.tipo = 'reingreso_rechazo')            as reingresos,
  count(*)                                                       as movimientos_POBLACION,
  max(m.fecha_operacion) filter (where m.tipo = 'reingreso_rechazo')
                                                                 as ultimo_reingreso,
  max(m.fecha_operacion)                                         as ultimo_movimiento
from movimientos_stock m
where m.anulado_el is null;

-- ---------------------------------------------------------------------------
-- CORRE ANTES de envases_9, y en LAS DOS BASES. Es la unica oportunidad de
-- leer esto: despues del drop la columna no existe y la consulta no compila.
--
-- `con_envase_ATENCION` es lo que se PIERDE. Cero es lo esperado —la columna
-- se cableo el 16/09 y el CHECK del bloque 7, si se corrio, rechaza todo lo
-- que el codigo escribe— pero si NO es cero hay que mirarlo antes de seguir:
-- son reingresos a cajon grande que declararon una caja. Esa caja se tira
-- igual (17/09), asi que el dato no cambia ninguna cuenta; lo que cambia es
-- cuanto se estuvo inflando el stock de cajas por la pata `liberadas`, que le
-- sumaba EXACTAMENTE esas filas.
--
-- `vuelven_a_cajon` es la poblacion de la que salen, y los dos `max` son el
-- testigo: un cero con "ultimo reingreso hace tres semanas" es un cero que se
-- entiende, y un cero solo es un cero que tranquiliza por omision.
--
-- Palmala no vota para los conteos de actividad: esta parada. Ahi esto sirve
-- para una sola cosa, que es confirmar que el esquema de las dos bases no se
-- separo — o sea, que la columna estaba tambien alla.
