-- ============================================================================
-- BITÁCORA DE FICHAS DE LOGÍSTICA
-- ============================================================================
-- Cada alta, edición y borrado de una ficha deja una foto completa acá.
-- La tabla viva (fichas_logistica) NO cambia: ningún cálculo lee esta
-- bitácora — es solo para consultar qué decía una ficha antes de un cambio
-- (ej.: a qué artículo apuntaba antes de cambiarlo).
--
-- ADITIVO PURO: no modifica ninguna tabla existente. Se puede correr en
-- cualquier momento sin afectar nada de lo que ya anda.
-- Correr en las DOS bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

create table fichas_logistica_historial (
    id              bigint generated always as identity primary key,
    -- Sin FK a fichas_logistica a propósito: la ficha puede ya no existir
    -- (el borrado también deja foto).
    ficha_id        bigint not null,
    cliente_id      bigint not null references clientes (id),
    articulo_id     bigint not null references articulos (id),
    envase_id       bigint references envases (id),
    contenido_caja  numeric,
    unidad_venta    text not null,
    envase_variable boolean not null,
    nombre_cliente  text,
    codigo_cliente  text,
    evento          text not null check (evento in ('foto_inicial', 'alta', 'edicion', 'borrado')),
    registrado_en   timestamptz not null default now()
);

comment on table fichas_logistica_historial is
    'Bitácora append-only de fichas_logistica: foto completa de la ficha en cada alta/edición/borrado, escrita por la app en la misma transacción. Nada la lee para calcular: es solo consulta humana. Un cambio hecho a mano en la base NO queda registrado acá.';
comment on column fichas_logistica_historial.evento is
    'foto_inicial = seed de esta migración (estado al momento de crear la bitácora); alta/edicion = estado que quedó grabado tras el evento; borrado = estado final de lo que se borró.';

create index idx_fichas_historial_cliente
    on fichas_logistica_historial (cliente_id, registrado_en);

-- Foto inicial de las fichas existentes, fechada con el creado_en de cada
-- una. Las ediciones ANTERIORES a esta migración no se pueden reconstruir:
-- la bitácora real arranca acá.
insert into fichas_logistica_historial
    (ficha_id, cliente_id, articulo_id, envase_id, contenido_caja, unidad_venta,
     envase_variable, nombre_cliente, codigo_cliente, evento, registrado_en)
select id, cliente_id, articulo_id, envase_id, contenido_caja, unidad_venta,
       envase_variable, nombre_cliente, codigo_cliente, 'foto_inicial', creado_en
from fichas_logistica;

-- Verificación: las dos consultas tienen que devolver el mismo número.
-- select count(*) from fichas_logistica;
-- select count(*) from fichas_logistica_historial where evento = 'foto_inicial';
