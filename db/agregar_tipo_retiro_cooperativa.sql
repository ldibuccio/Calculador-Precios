-- ============================================================================
-- Tipo de retiro nuevo: Cooperativa.
--
-- La Cooperativa es un tercero: se le pasa la distribución para que vaya a
-- buscar la mercadería y no hay control sobre esa gente — se asume que la
-- retira. Una compra con tipo_retiro = 'Cooperativa' nace directamente con
-- el retiro hecho (estado_retiro 'retirado', retiro_origen 'cooperativa'):
-- nunca aparece como pendiente de retiro en Logística. La recepción en
-- Depósito sigue siendo la normal.
--
-- Correr en LAS DOS bases (Frutamax y Palmala) ANTES de mergear el código
-- que carga compras con este tipo. Registrar cada base en db/APLICADO.md.
-- ============================================================================

begin;

alter table compras drop constraint compras_tipo_retiro_check;
alter table compras add constraint compras_tipo_retiro_check
    check (tipo_retiro in ('Clark', 'Carro', 'Pases', 'Cooperativa'));

alter table compras drop constraint compras_retiro_origen_check;
alter table compras add constraint compras_retiro_origen_check
    check (retiro_origen in ('logistica', 'deposito', 'migracion', 'ingreso_directo', 'cooperativa'));

commit;

-- Después de correr esto en LAS DOS bases: correr la CONSULTA 1 de
-- db/verificar_esquema.sql en las dos y comparar — las firmas de "compras"
-- cambian y tienen que volver a coincidir entre sí.
