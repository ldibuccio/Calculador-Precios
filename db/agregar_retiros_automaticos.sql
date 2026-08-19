-- ============================================================================
-- Retiros automáticos: Carro y Cooperativa nacen retirados, con orígenes
-- renombrados a automatico_*.
--
-- Carro lo maneja un tercero que nunca va a entrar al sistema, y la
-- Cooperativa ídem: nadie tilda nunca esas compras en Logística, así que
-- nacen directamente con estado_retiro 'retirado'. El prefijo automatico_
-- en retiro_origen deja claro que lo marcó el sistema (los otros valores
-- dicen quién marcó: logistica, deposito, migracion) — "carro" a secas
-- diría cómo se transporta, que es otra cosa y ya vive en tipo_retiro.
--
-- Correr en LAS DOS bases (Frutamax y Palmala). El UPDATE renombra el valor
-- viejo 'cooperativa' en las filas que ya existan. Las compras de Carro que
-- estaban pendientes ANTES de este cambio quedan como están (la ruta
-- /logistica/retiro/Carro sigue viva, sin botón, para tildarlas).
-- ============================================================================

begin;

alter table compras drop constraint if exists compras_tipo_retiro_check;
alter table compras add constraint compras_tipo_retiro_check
    check (tipo_retiro in ('Clark', 'Carro', 'Pases', 'Cooperativa'));

alter table compras drop constraint if exists compras_retiro_origen_check;

update compras set retiro_origen = 'automatico_cooperativa' where retiro_origen = 'cooperativa';

alter table compras add constraint compras_retiro_origen_check
    check (retiro_origen in ('logistica', 'deposito', 'migracion', 'ingreso_directo',
                             'automatico_carro', 'automatico_cooperativa'));

commit;
