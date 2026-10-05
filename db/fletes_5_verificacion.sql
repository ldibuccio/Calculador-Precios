-- Verificacion de fletes_1 a fletes_4. SE CORRE APARTE de los do: pegada
-- a un do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
select 'fletes' as QUE_MIGRACION,
       (select count(*) from pg_class
         where relname in ('clientes_sucursales', 'fleteros', 'fleteros_camiones',
                           'fleteros_camiones_precios', 'fletes', 'fletes_sucursales',
                           'fletes_viajes', 'fletes_correcciones')
           and relkind = 'r') as tablas_de_8,
       (select count(*) from pg_constraint
         where conname in ('fletes_sucursales_con_pallets', 'fletes_viajes_partes_suman'))
         as checks_de_2,
       (select count(*) from pg_trigger
         where tgname = 'viaje_pagado_no_se_toca' and not tgisinternal) as trigger_de_1,
       (select string_agg(s.codigo || '=' || s.nombre, ' ' order by s.codigo)
          from clientes_sucursales s join clientes c on c.id = s.cliente_id
         where c.nombre = 'Día %') as sucursales_de_dia,
       (select count(*) from fleteros) as fleteros_0,
       (select count(*) from fletes) as fletes_0,
       (select count(distinct sucursal) from pedidos_sucursales) as POBLACION_codigos,
       (select max(fecha_operacion) from pedidos where anulado_el is null) as testigo_ultimo_pedido;
