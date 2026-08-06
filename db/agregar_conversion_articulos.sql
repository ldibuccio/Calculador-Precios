-- Tabla de conversion: como llama cada cliente (nombre y codigo propios) a
-- cada articulo de mi catalogo en su pedido por email. No existia en el
-- schema (ver el comentario en listar_articulos() de app/db.py, que ya
-- avisaba que esto se iba a manejar aparte). Segura de correr aunque ya
-- exista (if not exists).

create table if not exists conversion_articulos_cliente (
    id              bigint generated always as identity primary key,
    cliente_id      bigint not null references clientes (id),
    articulo_id     bigint not null references articulos (id),
    codigo_cliente  text, -- codigo que usa el cliente en su pedido (opcional, ej. 90039)
    nombre_cliente  text not null, -- nombre tal cual aparece en el email del cliente (ej. "MANZ ROJ ELE")
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    unique (cliente_id, nombre_cliente)
);

comment on table conversion_articulos_cliente is 'Como llama cada cliente a cada articulo (nombre y codigo propios), para interpretar sus pedidos por email.';
