-- Índices de rendimiento para las consultas de más volumen y más frecuencia.
-- Correr en las DOS bases (Frutamax y Palmala). Es 100% aditivo: no crea
-- tablas ni cambia columnas, y el código funciona igual sin ellos (solo
-- más lento) — no hay ventana de riesgo ni orden de deploy que cuidar.
--
-- Criterio: SOLO índices que responden a consultas reales del código, con
-- la pantalla que los justifica anotada al lado. Nada "por las dudas":
-- cada índice hace las escrituras un poco más lentas, así que tiene que
-- pagarse con lecturas frecuentes.

begin;

-- === compras (la tabla que más crece) ===

-- Buscar Compras, Consultar Retiros, costeo, exportes, compras del día
-- por proveedor (corre en cada guardado de comanda): todos filtran por
-- fecha_operacion, casi siempre con proveedor_id encima.
create index if not exists compras_fecha_proveedor_idx
    on compras (fecha_operacion, proveedor_id);

-- El contador y la lista de "compras sin precio". El contador corre en
-- CADA visita a los hubs de Compras y Comercial: parcial para que sea
-- diminuto (solo las filas sin precio) y la fecha adentro porque la
-- lista ordena por fecha_operacion.
create index if not exists compras_sin_precio_idx
    on compras (fecha_operacion) where importe is null;

-- Pendientes de recepción (pantalla de Depósito, muchas veces por día).
-- Parcial: las compras ya procesadas salen del índice solas.
create index if not exists compras_pendientes_recepcion_idx
    on compras (guia_id, guia_punto) where estado = 'pendiente' and guia_id is not null;

-- "Procesados hoy" de Recepción y de Retiro: rango de un día sobre la
-- fecha de procesamiento (las consultas se reescribieron a rango — ver
-- listar_compras_procesadas_hoy_* en app/db.py — porque el ::date
-- anterior no podía usar ningún índice).
create index if not exists compras_procesada_el_idx
    on compras (procesada_el) where procesada_el is not null;
create index if not exists compras_retiro_procesado_el_idx
    on compras (retiro_procesado_el) where retiro_procesado_el is not null;

-- Pendientes de retiro (pantalla de Logística por tipo de retiro).
-- El predicado calca el filtro de listar_compras_pendientes_retiro,
-- incluidos los IS DISTINCT FROM (los NULL raros tienen que seguir
-- apareciendo, no desaparecer del índice).
create index if not exists compras_pendientes_retiro_idx
    on compras (tipo_retiro)
    where estado_retiro is distinct from 'retirado' and estado_retiro is distinct from 'cancelado';

-- Limpieza de fotos viejas (Sistema) y borrado de compras con foto:
-- agrupan/buscan por foto_ruta. Parcial: solo las filas con foto.
create index if not exists compras_foto_ruta_idx
    on compras (foto_ruta, fecha_operacion) where foto_ruta is not null;

-- === Vacíos (el camino de escritura del puesto) ===

-- _stock_vacios_actual suma por proveedor+tipo en CADA devolución,
-- conteo y ajuste (la foto stock_sistema), y estas tablas nunca se
-- borran. Parcial sin anulados (el stock los excluye siempre) e INCLUDE
-- cantidad para que el SUM salga del índice sin tocar la tabla.
create index if not exists vacios_recibidos_stock_idx
    on vacios_recibidos (proveedor_id, tipo_envase_id) include (cantidad)
    where anulado_el is null;
create index if not exists vacios_devueltos_stock_idx
    on vacios_devueltos (proveedor_id, tipo_envase_id) include (cantidad)
    where anulado_el is null;
create index if not exists ajustes_vacios_stock_idx
    on ajustes_vacios (proveedor_id, tipo_envase_id) include (cantidad)
    where anulado_el is null;

commit;
