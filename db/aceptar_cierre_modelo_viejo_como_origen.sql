-- El lote del compensatorio es un origen válido de consumo.
-- Un compensatorio POSITIVO entra al FIFO como lote (las entradas son
-- "movimientos_stock con cantidad > 0"), es el MÁS VIEJO del artículo —está
-- fechado el día anterior al corte— y por eso toda guía R de ese artículo lo
-- toca. Sin esto, el INSERT del consumo viola el check y el reproceso
-- REVIENTA con un error crudo delante del operario.
-- Se agrega el valor en vez de mapearlo a 'ajuste' a propósito:
-- reprocesos_consumos es un documento CONGELADO que no se corrige nunca, y
-- meter el compensatorio bajo el tipo de otra cosa es exactamente el error
-- de los saldos iniciales de Vacíos cargados por Ajustes.
do $$
begin
  if exists (select 1 from pg_constraint
             where conname = 'reprocesos_consumos_origen_check') then
    alter table reprocesos_consumos drop constraint reprocesos_consumos_origen_check;
  end if;
  alter table reprocesos_consumos add constraint reprocesos_consumos_origen_check
    check (origen in ('compra', 'ajuste', 'reingreso_rechazo', 'reproceso',
                      'stock_inicial', 'sin_lote', 'cierre_modelo_viejo'));
  comment on column reprocesos_consumos.origen is
    'compra (lote de guía de compra), ajuste (ej. stock inicial), reingreso_rechazo, reproceso (primera de otra guía R), cierre_modelo_viejo (el lote que el compensatorio positivo del corte le crea a un artículo que estaba en negativo: mercadería que no existe y sin costo posible), o sin_lote. sin_lote YA NO SE ESCRIBE: desde el 02/09 el freno no deja cargar una guía R que los lotes no cubran. El valor queda en el check por las guías viejas que lo tienen.';
end $$;

select conname, pg_get_constraintdef(oid) definicion
from pg_constraint where conname = 'reprocesos_consumos_origen_check';
