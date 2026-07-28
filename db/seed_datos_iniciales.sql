-- ============================================================================
-- Calculador de Precios — Datos iniciales
--
-- Carga los parámetros del negocio y los 29 artículos del catálogo. Correr
-- DESPUÉS de db/schema.sql, a mano en el editor SQL de Supabase.
--
-- Los datos de artículos salen de core/fichas.py (verificado: coinciden los
-- 29). El costo de envase en pesos NO se guarda en articulos: se deriva de
-- tipo_envase + los parámetros costo_envase_chico / costo_envase_grande de
-- más abajo, para no duplicar ese número en cada artículo.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. Parámetros del negocio
-- vigente_desde = '2020-01-01' como fecha "desde siempre" (no hay historial
-- previo real todavía). Si preferís otra fecha de arranque, cambiala acá.
-- ----------------------------------------------------------------------------
insert into parametros_historial (nombre_parametro, valor, vigente_desde) values
    ('descuento_estandar',   0.23, '2020-01-01'),
    ('utilidad_estandar',    0.20, '2020-01-01'),
    ('costo_envase_chico',   650,  '2020-01-01'),
    ('costo_envase_grande',  1600, '2020-01-01'),
    ('kg_por_palet',         800,  '2020-01-01');


-- ----------------------------------------------------------------------------
-- 2. Artículos
-- Columnas: nombre, tipo_envase, unidad_venta, contenido_caja,
-- cubetas_por_caja, unidades_por_cajon, kg_por_cajon
-- ----------------------------------------------------------------------------

-- Envase perdido, por kilo (11)
insert into articulos (nombre, tipo_envase, unidad_venta, contenido_caja, cubetas_por_caja, unidades_por_cajon, kg_por_cajon) values
    ('Cereza',      'perdido', 'kilo', null, null, null, null),
    ('Ciruela',     'perdido', 'kilo', null, null, null, null),
    ('Durazno',     'perdido', 'kilo', null, null, null, null),
    ('Man Gob',     'perdido', 'kilo', null, null, null, null),
    ('Melón',       'perdido', 'kilo', null, null, null, null),
    ('Mzn Granny',  'perdido', 'kilo', null, null, null, null),
    ('Mzn Red',     'perdido', 'kilo', null, null, null, null),
    ('Pelón',       'perdido', 'kilo', null, null, null, null),
    ('Pera',        'perdido', 'kilo', null, null, null, null),
    ('Sandía',      'perdido', 'kilo', null, null, null, null),
    ('Uva',         'perdido', 'kilo', null, null, null, null);

-- Envase perdido, por cubeta (2) — 12 cubetas por caja
insert into articulos (nombre, tipo_envase, unidad_venta, contenido_caja, cubetas_por_caja, unidades_por_cajon, kg_por_cajon) values
    ('Frutilla',  'perdido', 'cubeta', null, 12, null, null),
    ('Arándano',  'perdido', 'cubeta', null, 12, null, null);

-- Caja chica ($650), por kilo (8)
insert into articulos (nombre, tipo_envase, unidad_venta, contenido_caja, cubetas_por_caja, unidades_por_cajon, kg_por_cajon) values
    ('Lima',            'caja_chica', 'kilo', 5, null, null, null),
    ('Tomate Redondo',  'caja_chica', 'kilo', 6, null, null, null),
    ('Tomate Perita',   'caja_chica', 'kilo', 6, null, null, null),
    ('Berenjena',       'caja_chica', 'kilo', 6, null, null, null),
    ('Pepino',          'caja_chica', 'kilo', 6, null, null, null),
    ('Zapallito',       'caja_chica', 'kilo', 6, null, null, null),
    ('Morrón Verde',    'caja_chica', 'kilo', 4, null, null, null),
    ('Tomate Cherry',   'caja_chica', 'kilo', 5, null, null, null);

-- Caja chica ($650), por unidad (2) — con datos de palet
insert into articulos (nombre, tipo_envase, unidad_venta, contenido_caja, cubetas_por_caja, unidades_por_cajon, kg_por_cajon) values
    ('Mango',  'caja_chica', 'unidad', 10, null, 40, 16),
    ('Palta',  'caja_chica', 'unidad', 50, null, 80, 10);

-- Caja grande ($1600), por kilo (6)
insert into articulos (nombre, tipo_envase, unidad_venta, contenido_caja, cubetas_por_caja, unidades_por_cajon, kg_por_cajon) values
    ('Mandarina',     'caja_grande', 'kilo', 16, null, null, null),
    ('Limón',         'caja_grande', 'kilo', 16, null, null, null),
    ('Jugo',          'caja_grande', 'kilo', 16, null, null, null),
    ('Ombligo',       'caja_grande', 'kilo', 16, null, null, null),
    ('Pomelo',        'caja_grande', 'kilo', 16, null, null, null),
    ('Morrón Rojo',   'caja_grande', 'kilo', 8,  null, null, null);
