-- LA MERMA QUE SÍ SE REGISTRA: la del reproceso, en cada guía R.
--
-- Escrita porque la conclusión "la baja no se registra en ninguna columna"
-- era FALSA, y estuvo a punto de entrar a CLAUDE.md como hecho. Se había
-- mirado `movimientos_stock` (tipo 'merma' y 'ajuste') y `remitos_segunda`,
-- que son las tres puertas de la baja de GALPÓN. `reprocesos.bultos_merma`
-- es la cuarta y no se parece a las otras: no es un movimiento, es una
-- columna de la guía R, y la carga el operario en cada armado.
--
-- Las dos mermas NO son la misma cosa y por eso van separadas:
--   - la del REPROCESO: lo que se descarta al reenvasar. Se registra.
--   - la de GALPÓN: la fruta que se pudre esperando. Ésa no tiene registro.
--
-- Si esta consulta da distinto de cero, entonces sí hay costumbre de cargar
-- merma —adentro del armado— y la pantalla nueva no está creando el hábito
-- desde cero: le está dando puerta al caso que hoy no la tiene.
--
-- `tipo = 'inicial'` va aparte: esas guías PRODUCEN SIN CONSUMIR (las cajas
-- que ya estaban armadas el día del corte), así que su merma no es
-- comparable con lo tomado y mezclarlas ensucia la proporción.
with c0 as (select fecha as f0 from corte_modelo where id = 1)
select
    (select f0 from c0)                                            as corte,
    count(*) filter (where r.fecha_operacion > (select f0 from c0)
                       and r.anulado_el is null and r.tipo = 'normal')  as guias_r,
    count(*) filter (where r.fecha_operacion > (select f0 from c0)
                       and r.anulado_el is null and r.tipo = 'normal'
                       and r.bultos_merma > 0)                     as con_merma,
    coalesce(sum(r.bultos_merma) filter (
        where r.fecha_operacion > (select f0 from c0)
          and r.anulado_el is null and r.tipo = 'normal'), 0)      as bultos_merma,
    coalesce(sum(r.bultos_tomados) filter (
        where r.fecha_operacion > (select f0 from c0)
          and r.anulado_el is null and r.tipo = 'normal'), 0)      as bultos_tomados,
    count(*) filter (where r.anulado_el is null and r.tipo = 'inicial') as guias_iniciales,
    count(*) filter (where r.anulado_el is null)                   as historia_guias,
    max(r.fecha_operacion) filter (where r.anulado_el is null)     as ultima_guia_r
from reprocesos r;
