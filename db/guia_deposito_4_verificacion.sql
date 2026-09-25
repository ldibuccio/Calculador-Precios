select
  'guia_deposito' as QUE_MIGRACION,
  (select count(*) from information_schema.columns
    where table_name = 'guias_compra' and column_name = 'de_deposito') as columna,
  (select count(*) from pg_constraint where conname = 'guias_compra_dia_proveedor_origen'
      and pg_get_constraintdef(oid) like '%de_deposito%') as unico_nuevo,
  (select count(*) from pg_constraint
    where conrelid = 'guias_compra'::regclass and contype = 'u') as unicos_en_total,
  (select count(*) from compras c join guias_compra g on g.id = c.guia_id
    where (c.retiro_origen is not distinct from 'ingreso_directo') <> g.de_deposito) as mal_ubicadas,
  (select count(*) from guias_compra where de_deposito) as guias_de_deposito,
  (select count(*) from guias_compra g where g.de_deposito
      and exists (select 1 from fotos_guia f where f.guia_id = g.id)) as deposito_con_fotos,
  (select count(*) from compras where retiro_origen = 'ingreso_directo') as ingresos_directos_POBLACION,
  (select max(fecha_operacion) from compras where retiro_origen = 'ingreso_directo') as ultimo_ingreso;

-- Aparte de los `do`, en las DOS bases. Tiene DOS resultados buenos, según
-- la fase:
--   después del bloque 1 (antes del deploy): 1 · 1 · 2 · (mal_ubicadas > 0 es
--     normal todavía: los ingresos directos siguen en la guía del Puesto)
--   después de los bloques 2 y 3:            1 · 1 · 1 · 0
-- `deposito_con_fotos` tiene que dar 0: una guía de depósito con fotos es una
-- que creó Depósito y a la que Compras le colgó una comanda después, y ésa no
-- se puede separar sola — si da más de 0, me pasás el número y la miramos.
