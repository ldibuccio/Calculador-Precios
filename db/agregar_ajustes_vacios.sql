-- ============================================================================
-- Ajustes de stock en Vacíos (cajera).
--
-- Es un movimiento más, NUNCA pisa el stock: fila nueva con motivo
-- obligatorio y la foto del sistema del momento — si se pudiera escribir un
-- número arriba del stock sin dejar rastro, cualquier faltante se taparía
-- con un ajuste y se acaba el control cruzado.
--
-- El stock pasa a ser: recibidos − devueltos + ajustes (sin anulados).
--
-- Correr en LAS DOS bases (Frutamax y Palmala) ANTES de mergear el código.
-- Inofensivo para el código que corre hoy: tabla nueva que nadie lee.
-- ============================================================================

begin;

create table ajustes_vacios (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint not null references proveedores_puesto (id),
    tipo_envase_id  bigint not null references tipos_envase_puesto (id),
    cantidad        integer not null check (cantidad <> 0),
    motivo          text not null check (btrim(motivo) <> ''),
    stock_sistema   integer not null,
    creado_en       timestamptz not null default now(),
    anulado_el      timestamptz
);

comment on table ajustes_vacios is 'Ajustes de stock de Vacíos (cajera). Es un movimiento más, NUNCA pisa el stock: fila nueva con motivo obligatorio y la foto del sistema del momento — si se pudiera escribir un número arriba del stock sin dejar rastro, cualquier faltante se taparía con un ajuste y se acaba el control cruzado. El stock pasa a ser recibidos − devueltos + ajustes.';
comment on column ajustes_vacios.cantidad is 'Cajones del ajuste: positiva suma, negativa resta. Nunca 0.';
comment on column ajustes_vacios.motivo is 'Motivo obligatorio, escrito a mano. Sin motivo no se guarda (el CHECK lo garantiza también en la base).';
comment on column ajustes_vacios.stock_sistema is 'Stock del sistema (recibidos − devueltos + ajustes, SIN este ajuste) en el instante de guardar — misma foto que en devoluciones y conteos.';
comment on column ajustes_vacios.anulado_el is 'NULL = ajuste vigente. Igual que los demás movimientos: anular deja el registro visible, nunca se borra.';

commit;
