-- ============================================================================
-- COSTOS FIJOS (módulo nuevo en Gerencia) — tanda 1
-- ============================================================================
-- Los gastos fijos mensuales de la empresa, para saber cuánto cuesta
-- operar. Plan de cuentas de DOS niveles con numeración elegida por el
-- dueño (grupo entero: 10, 20...; subcuenta con decimal: 10.1, 10.2) y
-- espaciada para que entren cuentas nuevas sin renumerar.
--
-- El MECANISMO (reglas del dueño, innegociables):
-- 1. Se carga el importe UNA vez con su mes (la foto) y el sistema lo
--    infla mes a mes con el índice de inflación mensual. El valor inflado
--    es un CÁLCULO, jamás un dato guardado: se guarda la foto y la tabla
--    de índices, el valor de cada mes se deriva siempre (misma lógica que
--    el stock derivado).
-- 2. La corrección vale DE AHÍ EN ADELANTE: es una foto nueva con su mes;
--    los meses anteriores siguen resolviendo a la foto vieja con los
--    índices de entonces. Un error puntual se corrige con una foto
--    'solo_este_mes' que pisa SOLO ese mes, sin arrastrar.
-- 3. Si falta el índice de un mes, se AVISA — nunca se usa el anterior ni
--    se inventa: la subcuenta queda sin calcular, visible.
--
-- Bajas lógicas con MES (baja_desde): un sueldo dado de baja deja de
-- contar desde ese mes; los anteriores lo siguen contando. Nunca DELETE.
--
-- El seed de abajo carga el plan de cuentas BASE confirmado por el dueño
-- (25/08); los sueldos por persona (10.1...) los carga él desde la
-- pantalla con los nombres reales.
--
-- ADITIVO PURO: crea tablas nuevas, no toca nada existente. Correr en las
-- DOS bases (Frutamax y Palmala) y marcar en APLICADO.md. El código que
-- usa estas tablas se mergea recién después de la confirmación.
-- ============================================================================

create table grupos_costos_fijos (
    id bigint generated always as identity primary key,
    numero integer not null unique check (numero > 0),
    nombre text not null check (btrim(nombre) <> ''),
    creado_en timestamptz not null default now(),
    baja_el timestamptz
);

create table subcuentas_costos_fijos (
    id bigint generated always as identity primary key,
    grupo_id bigint not null references grupos_costos_fijos(id),
    numero integer not null check (numero > 0),
    nombre text not null check (btrim(nombre) <> ''),
    creado_en timestamptz not null default now(),
    -- Primer día del MES desde el que ya no cuenta (baja lógica con mes).
    baja_desde date check (baja_desde is null or extract(day from baja_desde) = 1),
    unique (grupo_id, numero)
);

create table importes_costos_fijos (
    id bigint generated always as identity primary key,
    subcuenta_id bigint not null references subcuentas_costos_fijos(id),
    -- Primer día del mes de la foto: el importe vale tal cual en ese mes.
    mes_desde date not null check (extract(day from mes_desde) = 1),
    importe numeric not null check (importe >= 0),
    alcance text not null default 'en_adelante'
        check (alcance in ('en_adelante', 'solo_este_mes')),
    creado_en timestamptz not null default now(),
    anulado_el timestamptz
);

create table indices_inflacion (
    -- Primer día del mes. El % es la inflación DE ese mes (respecto del
    -- anterior): la foto de agosto se multiplica por el % de septiembre
    -- para valer en septiembre. Puede ser negativo.
    mes date primary key check (extract(day from mes) = 1),
    porcentaje numeric not null,
    actualizado_en timestamptz not null default now()
);

create index importes_costos_fijos_subcuenta_idx
    on importes_costos_fijos (subcuenta_id, mes_desde)
    where anulado_el is null;

comment on table grupos_costos_fijos is
    'Plan de cuentas de Costos Fijos, nivel padre. El número lo elige el dueño (10 = Sueldos): espaciado para que entren grupos nuevos sin renumerar.';
comment on table subcuentas_costos_fijos is
    'Plan de cuentas de Costos Fijos, nivel hijo (10.1 = grupo 10, subcuenta 1). Los importes viven SOLO acá; el grupo agrega. baja_desde: primer mes que ya no cuenta (baja lógica con mes, nunca DELETE).';
comment on table importes_costos_fijos is
    'Las FOTOS de importe de cada subcuenta. El valor de un mes se CALCULA siempre: última foto en_adelante <= mes, inflada por los índices posteriores; una foto solo_este_mes pisa únicamente su mes. Corregir = foto nueva (la serie es el historial); error = anular y recargar.';
comment on table indices_inflacion is
    'Índice de inflación mensual, cargado por el dueño (editable: es un parámetro, no un hecho — editar un mes pasado recalcula los meses que lo usan). Si falta el de un mes, el sistema AVISA y no calcula: jamás inventa.';

-- ---------------------------------------------------------------------------
-- Seed del plan de cuentas base (confirmado por el dueño el 25/08).
-- Los sueldos por persona (10.1, 10.2...) se cargan desde la pantalla.
-- ---------------------------------------------------------------------------

insert into grupos_costos_fijos (numero, nombre) values
    (10, 'Sueldos'),
    (20, 'Cargas sociales'),
    (30, 'Impuestos'),
    (40, 'Ocupación'),
    (50, 'Servicios profesionales'),
    (60, 'Insumos y consumos'),
    (70, 'Mantenimiento y equipos'),
    (80, 'Varios');

insert into subcuentas_costos_fijos (grupo_id, numero, nombre)
select g.id, s.numero, s.nombre
from (values
    (20, 1, 'Cargas sociales'),
    (20, 2, 'Aguinaldos'),
    (20, 3, 'Sindicato'),
    (20, 4, 'Indemnizaciones'),
    (20, 5, 'Extra empleados'),
    (30, 1, 'IIBB'),
    (30, 2, 'Retenciones IIBB'),
    (30, 3, 'IVA'),
    (30, 4, 'Autónomos'),
    (30, 5, 'Moratorias'),
    (30, 6, 'Impuestos varios'),
    (40, 1, 'Canon y tasa'),
    (40, 2, 'Luz'),
    (40, 3, 'Seguridad'),
    (40, 4, 'Teléfono'),
    (40, 5, 'Internet'),
    (50, 1, 'Contador'),
    (50, 2, 'Sistemas de computación'),
    (50, 3, 'Sistema Market'),
    (50, 4, 'Seguros'),
    (60, 1, 'Limpieza'),
    (60, 2, 'Alimentos'),
    (60, 3, 'Farmacia'),
    (60, 4, 'Librería'),
    (60, 5, 'Imprenta'),
    (60, 6, 'Embalajes'),
    (60, 7, 'Ropa de trabajo'),
    (70, 1, 'Mantenimiento'),
    (70, 2, 'Clark'),
    (70, 3, 'Aserradero'),
    (70, 4, 'Muebles y frío'),
    (70, 5, 'Biodomo'),
    (80, 1, 'Representación'),
    (80, 2, 'Varios')
) as s (grupo_numero, numero, nombre)
join grupos_costos_fijos g on g.numero = s.grupo_numero;

-- Verificación: 4 tablas, 8 grupos y 34 subcuentas.
-- select table_name from information_schema.tables
--  where table_name in ('grupos_costos_fijos', 'subcuentas_costos_fijos',
--                       'importes_costos_fijos', 'indices_inflacion');
-- select count(*) from grupos_costos_fijos;      -- 8
-- select count(*) from subcuentas_costos_fijos;  -- 34
