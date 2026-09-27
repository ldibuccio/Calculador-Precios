with q as (select id from proveedores
            where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'DONLAZZARO')
select 'lazzaro_1_y_2' as QUE_MIGRACION,
  (select count(*) from proveedores_codigos where codigo = 'N09P39') as testigo_frutamax,
  (select count(*) from proveedores
    where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'PRODUCTOSDONLAZZARO'
  ) as PRODUCTOS_que_queda,
  (select count(*) from q) as DON_LAZZARO,
  (select string_agg(p.codigo_puesto || coalesce(' + ' || (select string_agg(codigo, ' + ')
            from proveedores_codigos pc where pc.proveedor_id = p.id), ''), ' | ')
     from proveedores p where p.id in (select id from q)) as codigos_de_LAZZARO,
  (select string_agg(codigo_llegada || ': ' || n, ' · ') from (
     select codigo_llegada, count(*) n from compras
      where proveedor_id in (select id from q) group by 1 order by 1) s) as compras_de_LAZZARO,
  (select count(*) from compras c where c.codigo_llegada is null) as compras_SIN_codigo,
  (select count(*) from proveedores_codigos) as codigos_alternativos,
  (select count(*) from proveedores) as POBLACION_proveedores,
  (select max(procesada_el)::date from compras) as ultima_recepcion;

-- Correr DESPUÉS de los dos bloques, en las dos bases. Frutamax: testigo 1 ·
-- PRODUCTOS 0 · DON LAZZARO 1 · L02P42 + L02P44 · compras L02P42: 14 · L02P44:
-- 1 · sin código 0 · alternativos 2 · proveedores 40. Palmala: testigo 0 y
-- todo como estaba (alternativos 0, proveedores 44).
