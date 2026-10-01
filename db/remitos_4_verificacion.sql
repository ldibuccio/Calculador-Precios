-- Verificacion de remitos_1 a remitos_3. SE CORRE APARTE de los do: pegada
-- a un do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
select 'remitos' as QUE_MIGRACION,
       (select count(*) from pg_class
         where relname in ('remitos', 'remitos_renglones', 'remitos_fotos')
           and relkind = 'r') as tablas_de_3,
       (select count(*) from pg_indexes
         where indexname in ('remitos_numero_por_cliente', 'remitos_uno_vivo_por_orden',
                             'remitos_renglones_por_renglon', 'remitos_fotos_por_remito'))
         as indices_de_4,
       (select count(*) from pg_constraint
         where conname in ('remitos_factura_coherente', 'remitos_factura_despues_de_recibir',
                           'remitos_anulado_con_motivo', 'remitos_facturado_no_se_anula',
                           'remitos_renglones_rechazo_tope', 'remitos_renglones_recibido_entero'))
         as checks_de_6,
       (select count(*) from pedidos_sucursales) as POBLACION_ordenes_de_compra,
       (select max(fecha_operacion) from pedidos where anulado_el is null) as testigo_ultimo_pedido;
