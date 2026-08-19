-- ============================================================================
-- Token anti-duplicado para la carga de comandas por foto.
--
-- El problema real: se corta internet mientras se guardan varias comandas.
-- El server puede haber guardado y commiteado, pero el teléfono nunca ve la
-- respuesta y reintenta el mismo guardado — antes eso duplicaba la comanda
-- entera. Ahora el server genera un token único por comanda al armar la
-- pantalla de revisión, todos los renglones se guardan con él, y si llega un
-- guardado con un token que ya existe en la base, no se inserta nada (ver
-- crear_compras_de_comanda en app/db.py).
--
-- Correr en LAS DOS bases (Frutamax y Palmala) ANTES de mergear el código
-- (el código nuevo escribe esta columna). Inofensivo para el código que
-- corre hoy: columna nullable que nadie escribe todavía.
-- ============================================================================

begin;

alter table compras add column if not exists carga_token text;
create index if not exists compras_carga_token_idx on compras (carga_token);

comment on column compras.carga_token is 'Token único por comanda leída por foto, generado por el server al armar la pantalla de revisión. Todos los renglones de una misma comanda comparten el token: si el teléfono reintenta un guardado cuya respuesta se perdió (corte de internet), el server lo reconoce y no duplica nada. NULL en compras cargadas a mano o anteriores a este cambio.';

commit;
