with v as (select current_date - 90 as desde)
select
  'primera_cero_1'                                        as QUE_CONSULTA,
  (select desde from v)                                   as desde,
  count(*)                                                as normales_POBLACION,
  count(*) filter (where r.bultos_primera = 0)            as PRIMERA_EN_CERO,
  coalesce(sum(r.bultos_tomados)
           filter (where r.bultos_primera = 0), 0)        as cajones_que_tomaron,
  coalesce(sum(r.costo_total)
           filter (where r.bultos_primera = 0), 0)        as PLATA_QUE_NO_SE_PEGA,
  count(*) filter (where r.bultos_primera = 0
                     and r.costo_total is null)           as ni_costo_pudo_calcular,
  count(*) filter (where r.bultos_primera = 0
                     and r.bultos_segunda > 0
                     and r.bultos_merma = 0)              as todo_a_SEGUNDA,
  count(*) filter (where r.bultos_primera = 0
                     and r.bultos_merma > 0
                     and r.bultos_segunda = 0)            as todo_a_MERMA,
  count(*) filter (where r.bultos_primera = 0
                     and r.bultos_segunda > 0
                     and r.bultos_merma > 0)              as mixto,
  count(*) filter (where r.bultos_primera = 0
                     and r.bultos_segunda = 0
                     and r.bultos_merma = 0)              as NI_UNA_NI_OTRA,
  max(r.fecha_operacion)                                  as ultima_guia_r
from reprocesos r, v
where r.anulado_el is null
  and r.tipo = 'normal'
  and r.fecha_operacion >= v.desde;

-- Cuántas guías R declararon CERO de primera, y cuánta plata quedó sin dónde
-- pegarse. Con `bultos_primera = 0` el server calcula `costo_total` y deja
-- `costo_por_bulto_primera` en NULL (app/db.py, "TODO el costo va a la
-- primera"), así que los cajones salieron del stock, costaron plata, y no hay
-- ningún bulto que la lleve: la primera de una guía entra al FIFO COMO UN
-- LOTE con ese costo, y sin primera no hay lote.
--
-- `NI_UNA_NI_OTRA` es el caso que no debería existir: tomó cajones y no
-- declaró ni segunda ni merma, o sea que no dice qué pasó con la fruta. La
-- ruta solo exige que ALGO se haya producido, así que es cargable.
--
-- Las dos columnas que hacen legible el resultado: `normales_POBLACION` (sin
-- ella, "3" no se puede leer) y `ultima_guia_r` (sin ella, un cero es
-- indistinguible del de una base parada). Solo vota FRUTAMAX.
