-- ============================================================================
-- Copia del catálogo por el navegador (alternativa a
-- scripts/copiar_catalogo_empresa.py, para hacerla entera desde el editor
-- SQL de Supabase, sin correr Python en ningún lado).
--
-- Cómo se usa, en orden:
--
--   0. En la base DESTINO ya tiene que estar corrido db/esquema_completo.sql.
--   1. En ORIGEN (Frutamax): correr la CONSULTA 0 (conteos) para ver los
--      tamaños. Solo lectura.
--   2. En ORIGEN: correr las consultas 1 a 8, UNA POR VEZ y en ese orden
--      (es el orden de dependencias de las claves foráneas). Cada una
--      devuelve una sola celda de texto con los INSERT de esa tabla:
--      tocar la celda para expandirla, copiar el contenido COMPLETO
--      (tiene que terminar en ";"), y pegarlo + correrlo en DESTINO
--      antes de pasar a la siguiente.
--   3. En DESTINO: correr el BLOQUE DE SECUENCIAS (al final de este
--      archivo). Sin esto, la primera alta nueva explota por ID duplicado.
--   4. Correr la CONSULTA 0 en las DOS bases y comparar los conteos.
--   5. En DESTINO: correr las CONSULTAS DE REVISIÓN y repasar a mano los
--      parámetros de cada cliente y los costos de envase (son los valores
--      de la empresa origen — solo un punto de partida).
--
-- Seguridad: los INSERT llevan los IDs de origen (OVERRIDING SYSTEM VALUE),
-- así las claves foráneas quedan bien apuntadas sin remapear nada. Y como
-- el ID es clave primaria, pegar dos veces la misma tanda falla entera por
-- duplicado y no inserta nada: no hay forma de duplicar el catálogo.
--
-- Las consultas 1 a 8 son SOLO LECTURA en origen: generan texto, no
-- escriben nada. Los valores van escapados con %L (comillas, acentos,
-- NULLs: todo queda bien armado solo).
-- ============================================================================


-- ----------------------------------------------------------------------------
-- CONSULTA 0 — Conteos por tabla. Correr en ORIGEN antes de empezar (para
-- ver tamaños) y en las DOS bases al final (para verificar la copia).
-- ----------------------------------------------------------------------------
select tabla, filas from (
    select 1 as orden, 'articulos' as tabla, count(*) as filas from articulos
    union all select 2, 'proveedores', count(*) from proveedores
    union all select 3, 'clientes', count(*) from clientes
    union all select 4, 'envases', count(*) from envases
    union all select 5, 'envases_costo_historial', count(*) from envases_costo_historial
    union all select 6, 'clientes_parametros_historial', count(*) from clientes_parametros_historial
    union all select 7, 'fichas_logistica', count(*) from fichas_logistica
    union all select 8, 'aprendizaje_articulos', count(*) from aprendizaje_articulos
) t order by orden;


-- ----------------------------------------------------------------------------
-- CONSULTA 1 — articulos
-- ----------------------------------------------------------------------------
select case when count(*) = 0 then '-- articulos: vacia, nada para copiar' else
    'INSERT INTO articulos (id, nombre, codigo_interno, cubetas_por_caja, unidades_por_cajon, kg_por_cajon, activo, creado_en, actualizado_en, merma_porcentaje, unidad_compra, contenido_referencia, grupo) OVERRIDING SYSTEM VALUE VALUES'
    || E'\n' || string_agg(
        format('(%L, %L, %L, %L, %L, %L, %L, %L, %L, %L, %L, %L, %L)',
            id, nombre, codigo_interno, cubetas_por_caja, unidades_por_cajon, kg_por_cajon,
            activo, creado_en, actualizado_en, merma_porcentaje, unidad_compra, contenido_referencia, grupo),
        E',\n' order by id)
    || ';'
end as sql_para_pegar_en_destino
from articulos;


-- ----------------------------------------------------------------------------
-- CONSULTA 2 — proveedores
-- ----------------------------------------------------------------------------
select case when count(*) = 0 then '-- proveedores: vacia, nada para copiar' else
    'INSERT INTO proveedores (id, nombre, creado_en, actualizado_en, codigo_puesto) OVERRIDING SYSTEM VALUE VALUES'
    || E'\n' || string_agg(
        format('(%L, %L, %L, %L, %L)', id, nombre, creado_en, actualizado_en, codigo_puesto),
        E',\n' order by id)
    || ';'
end as sql_para_pegar_en_destino
from proveedores;


-- ----------------------------------------------------------------------------
-- CONSULTA 3 — clientes
-- ----------------------------------------------------------------------------
select case when count(*) = 0 then '-- clientes: vacia, nada para copiar' else
    'INSERT INTO clientes (id, nombre, activo, creado_en, actualizado_en) OVERRIDING SYSTEM VALUE VALUES'
    || E'\n' || string_agg(
        format('(%L, %L, %L, %L, %L)', id, nombre, activo, creado_en, actualizado_en),
        E',\n' order by id)
    || ';'
end as sql_para_pegar_en_destino
from clientes;


-- ----------------------------------------------------------------------------
-- CONSULTA 4 — envases
-- ----------------------------------------------------------------------------
select case when count(*) = 0 then '-- envases: vacia, nada para copiar' else
    'INSERT INTO envases (id, cliente_id, nombre, activo, creado_en, actualizado_en) OVERRIDING SYSTEM VALUE VALUES'
    || E'\n' || string_agg(
        format('(%L, %L, %L, %L, %L, %L)', id, cliente_id, nombre, activo, creado_en, actualizado_en),
        E',\n' order by id)
    || ';'
end as sql_para_pegar_en_destino
from envases;


-- ----------------------------------------------------------------------------
-- CONSULTA 5 — envases_costo_historial
-- ----------------------------------------------------------------------------
select case when count(*) = 0 then '-- envases_costo_historial: vacia, nada para copiar' else
    'INSERT INTO envases_costo_historial (id, envase_id, costo, vigente_desde, creado_en) OVERRIDING SYSTEM VALUE VALUES'
    || E'\n' || string_agg(
        format('(%L, %L, %L, %L, %L)', id, envase_id, costo, vigente_desde, creado_en),
        E',\n' order by id)
    || ';'
end as sql_para_pegar_en_destino
from envases_costo_historial;


-- ----------------------------------------------------------------------------
-- CONSULTA 6 — clientes_parametros_historial
-- ----------------------------------------------------------------------------
select case when count(*) = 0 then '-- clientes_parametros_historial: vacia, nada para copiar' else
    'INSERT INTO clientes_parametros_historial (id, cliente_id, nombre_parametro, valor, vigente_desde, creado_en, tipo) OVERRIDING SYSTEM VALUE VALUES'
    || E'\n' || string_agg(
        format('(%L, %L, %L, %L, %L, %L, %L)',
            id, cliente_id, nombre_parametro, valor, vigente_desde, creado_en, tipo),
        E',\n' order by id)
    || ';'
end as sql_para_pegar_en_destino
from clientes_parametros_historial;


-- ----------------------------------------------------------------------------
-- CONSULTA 7 — fichas_logistica
-- ----------------------------------------------------------------------------
select case when count(*) = 0 then '-- fichas_logistica: vacia, nada para copiar' else
    'INSERT INTO fichas_logistica (id, articulo_id, cliente_id, unidad_venta, envase_id, contenido_caja, envase_variable, creado_en, actualizado_en, nombre_cliente, codigo_cliente) OVERRIDING SYSTEM VALUE VALUES'
    || E'\n' || string_agg(
        format('(%L, %L, %L, %L, %L, %L, %L, %L, %L, %L, %L)',
            id, articulo_id, cliente_id, unidad_venta, envase_id, contenido_caja,
            envase_variable, creado_en, actualizado_en, nombre_cliente, codigo_cliente),
        E',\n' order by id)
    || ';'
end as sql_para_pegar_en_destino
from fichas_logistica;


-- ----------------------------------------------------------------------------
-- CONSULTA 8 — aprendizaje_articulos
-- (la candidata a más grande: si el conteo pasa de unas 300 filas, conviene
-- partirla por rangos de id agregando "where id between ... and ..." acá y
-- copiando/pegando cada rango por separado)
-- ----------------------------------------------------------------------------
select case when count(*) = 0 then '-- aprendizaje_articulos: vacia, nada para copiar' else
    'INSERT INTO aprendizaje_articulos (id, proveedor_id, texto_leido, articulo_id, creado_en) OVERRIDING SYSTEM VALUE VALUES'
    || E'\n' || string_agg(
        format('(%L, %L, %L, %L, %L)', id, proveedor_id, texto_leido, articulo_id, creado_en),
        E',\n' order by id)
    || ';'
end as sql_para_pegar_en_destino
from aprendizaje_articulos;


-- ----------------------------------------------------------------------------
-- BLOQUE DE SECUENCIAS — correr en DESTINO, después de pegar las 8 tandas.
-- Deja cada secuencia de IDs apuntando al máximo copiado: sin esto, la
-- primera alta nueva (un artículo, un proveedor) explota por ID duplicado.
-- ----------------------------------------------------------------------------
select setval(pg_get_serial_sequence('articulos', 'id'), coalesce((select max(id) from articulos), 1));
select setval(pg_get_serial_sequence('proveedores', 'id'), coalesce((select max(id) from proveedores), 1));
select setval(pg_get_serial_sequence('clientes', 'id'), coalesce((select max(id) from clientes), 1));
select setval(pg_get_serial_sequence('envases', 'id'), coalesce((select max(id) from envases), 1));
select setval(pg_get_serial_sequence('envases_costo_historial', 'id'), coalesce((select max(id) from envases_costo_historial), 1));
select setval(pg_get_serial_sequence('clientes_parametros_historial', 'id'), coalesce((select max(id) from clientes_parametros_historial), 1));
select setval(pg_get_serial_sequence('fichas_logistica', 'id'), coalesce((select max(id) from fichas_logistica), 1));
select setval(pg_get_serial_sequence('aprendizaje_articulos', 'id'), coalesce((select max(id) from aprendizaje_articulos), 1));


-- ----------------------------------------------------------------------------
-- CONSULTAS DE REVISIÓN — correr en DESTINO al final. Son los valores que
-- vinieron de la empresa origen: cada empresa negocia sus propias
-- condiciones, esto es solo el punto de partida.
-- ----------------------------------------------------------------------------

-- Conceptos VIGENTES de cada cliente (descuentos, utilidad, IVA, etc.):
select c.nombre as cliente, h.nombre_parametro as parametro, h.tipo, h.valor, h.vigente_desde
from clientes_parametros_historial h
join clientes c on c.id = h.cliente_id
where h.vigente_desde = (
    select max(h2.vigente_desde) from clientes_parametros_historial h2
    where h2.cliente_id = h.cliente_id and h2.nombre_parametro = h.nombre_parametro
      and h2.vigente_desde <= current_date
)
order by c.nombre, h.tipo, h.nombre_parametro;

-- Costos de envase VIGENTES:
select c.nombre as cliente, e.nombre as envase, h.costo, h.vigente_desde
from envases_costo_historial h
join envases e on e.id = h.envase_id
join clientes c on c.id = e.cliente_id
where h.vigente_desde = (
    select max(h2.vigente_desde) from envases_costo_historial h2
    where h2.envase_id = h.envase_id and h2.vigente_desde <= current_date
)
order by c.nombre, e.nombre;
