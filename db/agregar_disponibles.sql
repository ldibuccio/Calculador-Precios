-- Disponibles: planilla de mercadería en stock que se manda por mail a
-- cada cliente (hoy se arma a mano en Excel, hoja "Stock Actualizado").
--
-- Dos tablas, mismo patrón cabecera + detalle que compras/proveedores:
--
-- disponibles: un renglón por planilla armada para un cliente, con el
-- rango de fechas mostrado en el Excel y su estado. Sin DEFAULT en
-- estado, mismo motivo que estado_retiro en compras: /compras/disponibles
-- lo escribe siempre explícito, nunca queda a cargo de la base.
--
-- Un cliente tiene a lo sumo UN borrador abierto a la vez (índice único
-- parcial): "Guardar" lo crea o lo sigue actualizando in place, para
-- poder retomarlo después. "Guardar y generar Excel" lo pasa a
-- 'generado' — a partir de ahí queda como historial (no se vuelve a
-- tocar); la próxima vez que se elige ese cliente, al no haber borrador,
-- se arranca uno nuevo precargado con los artículos/cantidades de ese
-- último 'generado'.
--
-- disponibles_detalle: un renglón (artículo + cantidad) de una planilla.
-- codigo/nombre se COPIAN como texto en el momento de guardar (desde
-- fichas_logistica.codigo_cliente/nombre_cliente, o tipeados a mano si el
-- artículo no tiene ficha para ese cliente) — misma disciplina que
-- precios_venta_historial: si mañana cambia la ficha del cliente, un
-- Disponible viejo no cambia con ella. articulo_id es nullable porque un
-- renglón puede cargarse 100% a mano (código y nombre tipeados), sin
-- ningún artículo del catálogo detrás.
--
-- orden es explícito (no se deriva de articulos.grupo al mostrar): así
-- los renglones tipeados a mano -que no tienen grupo, por no tener
-- articulo_id- también tienen un lugar fijo en la planilla. Se calcula
-- una vez al guardar (ver app/main.py), típicamente arrancando en el
-- orden fruta/hortaliza/pesada de la precarga.
--
-- version: cuenta los reenvíos del mismo cliente + fecha_desde el mismo
-- día (ej. se manda el Disponible a la mañana y hay que reenviar uno
-- actualizado a media mañana porque llegó mercadería nueva). NULL
-- mientras es borrador; se calcula y se fija recién al generar el Excel
-- (COUNT de 'generado' previos con ese mismo cliente_id+fecha_desde, +1).
-- El nombre del archivo lleva "_v2", "_v3", etc. a partir del segundo,
-- así nunca se pisa el que ya se mandó por mail.
--
-- Seguro de correr más de una vez (create table if not exists, create
-- unique index/constraint con manejo de "ya existe" no hace falta porque
-- son objetos nuevos). Solo aditivo: no toca ninguna tabla existente.
--
-- Correr a mano en el editor SQL de Supabase. NO se ejecuta acá.

create table if not exists disponibles (
    id              bigint generated always as identity primary key,
    cliente_id      bigint not null references clientes (id),
    fecha_desde     date not null,
    fecha_hasta     date not null,
    estado          text not null check (estado in ('borrador', 'generado')),
    version         integer,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    check (fecha_hasta >= fecha_desde)
);

comment on table disponibles is 'Cabecera de una planilla de Disponibles (mercadería en stock) para un cliente, con el rango de fechas mostrado en el Excel. borrador = se sigue editando (se puede retomar); generado = ya se bajó el Excel, queda como historial.';
comment on column disponibles.fecha_desde is 'Primer día del rango mostrado en el Excel como "Fecha: ...".';
comment on column disponibles.fecha_hasta is 'Último día del rango. Igual a fecha_desde si es un solo día (el Excel muestra "Fecha: DD/MM/AAAA"); si son dos días distintos, muestra "Fecha: DD/MM/AAAA al DD/MM/AAAA". CHECK fecha_hasta >= fecha_desde: agregado por el usuario al correr el SQL, para que un dedazo no deje un rango invertido.';
comment on column disponibles.estado is 'borrador o generado. Sin DEFAULT: /compras/disponibles siempre lo escribe explícito, nunca a cargo de la base.';
comment on column disponibles.version is 'Reenvío número N del mismo cliente+fecha_desde el mismo día (1 = el primero, sin sufijo en el archivo). NULL mientras es borrador; se fija recién al generar el Excel.';

create unique index if not exists disponibles_un_borrador_por_cliente_idx
    on disponibles (cliente_id)
    where estado = 'borrador';

comment on index disponibles_un_borrador_por_cliente_idx is 'Un cliente no puede tener dos borradores de Disponibles abiertos a la vez.';

create table if not exists disponibles_detalle (
    id              bigint generated always as identity primary key,
    disponible_id   bigint not null references disponibles (id) on delete cascade,
    articulo_id     bigint references articulos (id),
    codigo          text,
    nombre          text not null,
    cantidad        numeric not null,
    orden           integer not null,
    unique (disponible_id, orden)
);

comment on table disponibles_detalle is 'Un renglón (artículo + cantidad) de un Disponible. codigo/nombre se COPIAN como texto al guardar (desde fichas_logistica, o tipeados a mano) — igual disciplina que precios_venta_historial: un Disponible viejo no cambia si la ficha del cliente cambia después.';
comment on column disponibles_detalle.articulo_id is 'NULL si el renglón se escribió 100% a mano (sin ficha para este cliente) — codigo/nombre quedan igual, tipeados.';
comment on column disponibles_detalle.codigo is 'Código copiado de fichas_logistica.codigo_cliente al guardar (o tipeado a mano). Puede quedar vacío (ej. Frutilla, que hoy no tiene código).';
comment on column disponibles_detalle.nombre is 'Nombre copiado de fichas_logistica.nombre_cliente al guardar (o tipeado a mano, o el nombre interno del artículo si no tiene alias). Nunca vacío: es la columna Producto del Excel.';
comment on column disponibles_detalle.orden is 'Orden de aparición en la planilla, fijado al guardar (no se deriva de articulos.grupo en el momento de mostrar, para que los renglones tipeados a mano también tengan dónde ubicarse).';
