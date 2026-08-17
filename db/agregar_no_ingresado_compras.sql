-- Depósito / Recepción: tercera opción además de Recibir/Rechazar por
-- calidad — "No ingresó" (estado = 'no_ingresado'), para mercadería que
-- nunca llegó al depósito (no se la fueron a buscar, se perdió, etc.).
--
-- A diferencia de recepcionar_compra/rechazar_compra, marcar no_ingresado
-- NO marca la compra como retirada (ver _auto_retirar_si_corresponde en
-- app/db.py): si nunca llegó al depósito, no hay ninguna base para asumir
-- que sí se retiró del puesto en el Mercado. estado_retiro queda
-- exactamente como estaba.
--
-- Un CHECK no admite "agregarle un valor" directamente en Postgres: hay
-- que borrar el constraint viejo y crear uno nuevo con la lista completa.
-- Se lo referencia por el nombre que Postgres le puso por default
-- (compras_estado_check, generado al crear la columna con CHECK inline en
-- agregar_recepcion_compras.sql). Es un cambio aditivo (amplía la lista
-- de valores permitidos): no afecta ninguna fila existente, no hace falta
-- backfill. Seguro de correr más de una vez.

alter table compras drop constraint if exists compras_estado_check;

alter table compras add constraint compras_estado_check
    check (estado in ('pendiente', 'recepcionado', 'rechazado', 'no_ingresado'));

comment on column compras.estado is 'pendiente/recepcionado/rechazado/no_ingresado. no_ingresado = la mercadería nunca llegó al depósito (no se retiró del puesto en el Mercado, se perdió, etc.) — a diferencia de recepcionado/rechazado, NO marca la compra como retirada. NULL en compras cargadas antes del cambio original de Recepción.';

-- El significado de contenido_por_cajon_real y cantidad_kilos_real cambia
-- para artículos por kilo: Depósito ahora pesa UN bulto (no toda la carga
-- junta), así que contenido_por_cajon_real pasa a ser el dato que se tipea
-- directo, y cantidad_kilos_real el derivado (cajones × contenido) — antes
-- era al revés. Para unidad/cubeta no cambia nada: se sigue contando el
-- total (cantidad_fraccion_real) y contenido_por_cajon_real se sigue
-- derivando como promedio. Ningún dato viejo se toca, solo cambia cómo se
-- completan las columnas de acá en adelante.

comment on column compras.contenido_por_cajon_real is 'Contenido por cajón real. Para artículos por kilo: lo tipea Depósito directo (pesa un bulto). Para unidad/cubeta: derivado (cantidad_fraccion_real / cantidad_cajones_real), como antes.';
comment on column compras.cantidad_kilos_real is 'Kilos reales totales (solo artículos por kilo), derivado como cantidad_cajones_real × contenido_por_cajon_real. NULL = todavía no pesado, o el artículo no se compra por kilo.';
