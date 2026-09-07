-- ############################################################################
-- EL VALE QUE NO SE VA A COBRAR: se cancela lo que se debe SIN tocar el stock.
--
-- Dos hechos que hoy estaban pegados en un solo botón:
--   "esta recepción no existió"  -> afecta el stock
--   "el vale no se cobra nunca"  -> NO afecta el stock, los cajones están
--
-- NO se reusa `sena_anulada_el` para esto, y la razón vale escrita: haría
-- falta que convivan con `sena_vale_el`, o sea num_nonnulls = 2, y
-- `listar_senas_resueltas` filtra `num_nonnulls(...) = 1` — esas filas
-- DESAPARECERÍAN del historial de señas cerradas. Es el filtro que descarta lo
-- que no reconoce, otra vez. Una columna nueva no toca ese conteo.
--
-- Y el vale EXISTIÓ: taparlo con "anulada" pierde que hubo un papel, que es
-- justo lo que administración necesita si el cliente aparece con él.
--
-- IDEMPOTENTE: se puede correr de nuevo sin que reviente. El `add column if
-- not exists` ya lo era; el `add constraint` no, así que va con drop previo.
-- ############################################################################
do $$
begin
  alter table vacios_recibidos
    add column if not exists sena_vale_caducado_el timestamptz,
    add column if not exists sena_vale_caducado_motivo text;

  if exists (select 1 from pg_constraint
             where conname = 'vacios_recibidos_caducado_solo_con_vale') then
    alter table vacios_recibidos drop constraint vacios_recibidos_caducado_solo_con_vale;
  end if;

  alter table vacios_recibidos
    add constraint vacios_recibidos_caducado_solo_con_vale
    check (sena_vale_caducado_el is null
           or (sena_vale_el is not null and btrim(sena_vale_caducado_motivo) <> ''));

  comment on column vacios_recibidos.sena_vale_caducado_el is
    'El vale se dio por NO COBRADO (fecha). NO borra sena_vale_el: los dos conviven a proposito, porque el vale existio y el papel puede aparecer. Decision de administracion, desde Movimientos y detras de la clave de control. NO toca el stock: los cajones estan en el galpon. Un vale sin esta fecha sigue vivo, aunque tenga meses.';
  comment on column vacios_recibidos.sena_vale_caducado_motivo is
    'Por que se dio por no cobrado. Obligatorio (lo garantiza el check vacios_recibidos_caducado_solo_con_vale): el sistema no guarda QUIEN lo hizo —no hay login— asi que este texto es el unico rastro del porque. Se escribe pensando en el que lo lea en seis meses.';
end $$;

select conname, pg_get_constraintdef(oid) definicion
from pg_constraint where conname = 'vacios_recibidos_caducado_solo_con_vale';
