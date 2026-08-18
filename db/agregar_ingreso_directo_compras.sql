-- Ingreso directo de mercadería al Depósito (/deposito/ingresar), sin
-- pasar por Logística ni por Recepción como pasos separados: la carga
-- alguien del depósito que ya tiene la mercadería en la mano, pesada y
-- contada.
--
-- retiro_origen amplía su CHECK con un cuarto valor: 'ingreso_directo'.
-- No reusa 'deposito' porque ese valor ya significa otra cosa (auto-
-- retiro: Depósito recepcionó algo que SÍ pasó por el puesto del
-- Mercado) — si las dos guardaran el mismo valor, después no se podría
-- distinguir una de la otra.
--
-- Un CHECK no admite "agregarle un valor" directamente en Postgres: hay
-- que borrar el constraint viejo y crear uno nuevo con la lista completa
-- (mismo patrón que agregar_no_ingresado_compras.sql). Cambio aditivo:
-- no afecta ninguna fila existente, no hace falta backfill. Seguro de
-- correr más de una vez.

alter table compras drop constraint if exists compras_retiro_origen_check;

alter table compras add constraint compras_retiro_origen_check
    check (retiro_origen in ('logistica', 'deposito', 'migracion', 'ingreso_directo'));

comment on column compras.retiro_origen is 'Quién/qué lo marcó: logistica (a mano, desde /logistica), deposito (automático al recepcionar/rechazar algo que sí pasó por el puesto del Mercado), migracion (backfill de compras viejas) o ingreso_directo (nació directo en el depósito, cargada desde /deposito/ingresar, nunca pasó por Logística).';
