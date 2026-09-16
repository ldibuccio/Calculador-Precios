select
  (select count(*) from information_schema.columns
    where table_name = 'movimientos_stock'
      and column_name = 'lleva_caja_nuestra')                   as columna,
  (select count(*) from pg_constraint
    where conname = 'movimientos_stock_lleva_caja_solo_reproceso') as guarda_destino,
  (select count(*) from pg_constraint
    where conname = 'movimientos_stock_envase_coherente')       as guarda_coherencia,
  count(*) filter (where m.destino_rechazo = 'reproceso')        as vuelven_a_cajon,
  count(*) filter (where m.destino_rechazo = 'reproceso'
                     and m.lleva_caja_nuestra is null)           as sin_declarar,
  count(*) filter (where m.envase_id is not null)                as con_envase,
  count(*) filter (where m.lleva_caja_nuestra is true
                     and m.envase_id is null)                    as ofensores,
  count(*)                                                       as movimientos,
  max(m.fecha_operacion)                                         as ultimo_movimiento
from movimientos_stock m
where m.anulado_el is null;

-- ---------------------------------------------------------------------------
-- Verificacion del bloque 7. CORRE APARTE, nunca pegada al `do`: pegadas en
-- la misma corrida el editor se queda con la ultima y el `do` NO SE EJECUTA,
-- sin error y con "no rows", que es la salida normal de un `do` que si corrio.
--
-- SE CORRE EN LAS DOS BASES y la fila se pega CON EL NOMBRE DE LA BASE
-- ADELANTE: las columnas que importan dan lo mismo en las dos por diseno, asi
-- que las dos filas son indistinguibles entre si y pegar una creyendo que son
-- las dos es el error natural. `ultimo_movimiento` es el testigo que dice de
-- cual base es la fila, y si esa base vota.
--
-- Lo esperado: columna 1 · guarda_destino 1 · guarda_coherencia 1 ·
-- ofensores 0. Las tres primeras contadas POR NOMBRE, que es lo unico que
-- distingue "ya existia con otra definicion" de "se creo ahora".
--
-- `sin_declarar` es EL HUECO, y no es un ofensor: son los reingresos a cajon
-- grande anteriores a estas columnas, que liberaron una caja y no dicen cual.
-- Va al lado de `vuelven_a_cajon`, que es su poblacion — un conteo solo no se
-- puede leer. Se apaga solo: ningun reingreso nuevo puede entrar sin declarar.
