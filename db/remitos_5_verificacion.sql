-- Verificacion de remitos_1 a remitos_4. SE CORRE APARTE de los do: pegada
-- a un do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
select 'remitos' as QUE_MIGRACION,
       (select count(*) from pg_class
         where relname in ('remitos', 'remitos_renglones', 'remitos_fotos',
                           'remitos_numeros')
           and relkind = 'r') as tablas_de_4,
       (select count(*) from pg_indexes
         where indexname in ('remitos_numero_por_cliente', 'remitos_uno_por_orden',
                             'remitos_renglones_por_renglon', 'remitos_fotos_por_remito',
                             'remitos_numeros_por_remito'))
         as indices_de_5,
       (select count(*) from pg_constraint
         where conname in ('remitos_factura_coherente', 'remitos_factura_despues_de_recibir',
                           'remitos_renglones_recibidos_tope',
                           'remitos_renglones_recibido_entero', 'remitos_numeros_distinto'))
         as checks_de_5,
       (select count(*) from information_schema.columns
         where table_name = 'remitos' and column_name like 'anulado%') as anulado_en_0,
       (select count(*) from pedidos_sucursales) as POBLACION_ordenes_de_compra,
       (select max(fecha_operacion) from pedidos where anulado_el is null) as testigo_ultimo_pedido;
