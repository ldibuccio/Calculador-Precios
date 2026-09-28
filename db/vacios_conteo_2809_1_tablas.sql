create table if not exists vacios_deposito_arranques (
    id         bigint generated always as identity primary key,
    motivo     text not null check (btrim(motivo) <> ''),
    creado_en  timestamptz not null default now()
);

create table if not exists vacios_deposito_arranque_pilas (
    id             bigint generated always as identity primary key,
    arranque_id    bigint  not null references vacios_deposito_arranques (id),
    proveedor_id   bigint  not null references proveedores (id),
    marca_vacio_id bigint,
    cantidad       integer not null check (cantidad >= 0),
    constraint vacios_arr_marca_del_proveedor
        foreign key (marca_vacio_id, proveedor_id) references marcas_vacio (id, proveedor_id)
);

create index if not exists vacios_arr_pilas_arranque_idx
    on vacios_deposito_arranque_pilas (arranque_id);

comment on table vacios_deposito_arranques is 'Un CONTEO FÍSICO que reinicia el stock de vacíos del depósito. El último manda: desde su creado_en suma lo recibido con seña y resta lo devuelto; todo lo anterior (foto, recepciones, devoluciones, ajustes, asignaciones) queda como historia y no mueve el número.';
comment on table vacios_deposito_arranque_pilas is 'Lo contado en cada PILA (proveedor y marca; NULL = sin asignar) en ese arranque. Un proveedor o una pila que no está acá arranca en cero.';

select 'vacios_conteo_2809_1_tablas' as que_migracion,
       (select count(*) from information_schema.tables
         where table_name in ('vacios_deposito_arranques', 'vacios_deposito_arranque_pilas')) as tablas_de_2;

-- ARRANQUE DE VACÍOS DEL DEPÓSITO DESDE UN CONTEO FÍSICO (28/09), bloque 1.
-- Solo ESTRUCTURA: crea las dos tablas vacías. No cambia ningún número:
-- el código desplegado hoy no las lee. Se puede correr las veces que haga
-- falta. La consulta del final devuelve tablas_de_2 = 2.
-- Orden: 1 tablas, 2 datos, 3 buscadores, 4 revisar (solo lee),
-- 5 cargar (el único que escribe datos), 6 verificación (aparte).
