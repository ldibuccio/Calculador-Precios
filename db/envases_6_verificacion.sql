select
 (select count(*) from information_schema.columns
   where table_name = 'envases' and column_name = 'umbral_reposicion')      as col_umbral,
 (select count(*) from information_schema.tables
   where table_name = 'movimientos_envase')                                 as tabla_movimientos,
 (select count(*) from pg_constraint
   where conname in ('envases_umbral_no_negativo',
                     'movimientos_envase_origen_check',
                     'movimientos_envase_signo_segun_origen',
                     'movimientos_envase_ajuste_con_motivo'))               as guardas_contenido_de_4,
 (select count(*) from pg_indexes
   where indexname = 'movimientos_envase_un_conteo_inicial')                as indice_un_conteo,
 (select count(*) from information_schema.columns
   where table_name = 'reprocesos'
     and column_name in ('envase_id', 'lleva_caja_nuestra'))                as cols_reprocesos_de_2,
 (select count(*) from pg_constraint
   where conname = 'reprocesos_envase_coherente')                           as guarda_reprocesos,
 (select count(*) from information_schema.columns
   where table_name = 'movimientos_stock' and column_name = 'envase_id')    as col_mov_stock,
 (select count(*) from pg_constraint
   where conname in ('movimientos_stock_envase_solo_reproceso',
                     'movimientos_stock_proveedor_solo_devolucion',
                     'movimientos_stock_compra_solo_devolucion')
     and pg_get_constraintdef(oid) like '%IS DISTINCT FROM%')               as guardas_NULL_SAFE_de_3,
 (select count(*) from movimientos_stock
   where (proveedor_devolucion_id is not null or compra_devolucion_id is not null)
     and destino_rechazo is distinct from 'devolucion_proveedor')           as ofensores_viejos,
 (select count(*) from reprocesos where anulado_el is null)                 as guias_POBLACION,
 (select count(*) from envases)                                             as envases_catalogo,
 (select max(fecha_operacion) from reprocesos where anulado_el is null)     as ultima_guia_r;

-- ---------------------------------------------------------------------------
-- VA EN SU PROPIA CORRIDA: pegada a un `do`, el editor se queda con esta y el
-- `do` no se ejecuta, con la misma salida que uno que si corrio. En LAS DOS
-- BASES, y se pegan las DOS filas con el nombre de la base adelante.
--
-- Todo aplicado: 1 · 1 · 4 · 1 · 2 · 1 · 1 · 3 · ofensores_viejos 0.
--
-- guardas_NULL_SAFE_de_3 mira la DEFINICION y no el nombre: los tres
-- constraints existen en los dos estados. Con `=` da 0.
