-- Verificación de "un solo listado abierto". SE CORRE APARTE del bloque.
-- Tiene que dar: listados_compra_8_un_solo_abierto · 0 · 1 · 1 · <0 o 1> · <listados> · <fecha>.
-- POR DEFINICIÓN y no solo por nombre: el índice tiene que ser único y
-- parcial sobre 'borrador'. Uno con el nombre bueno y otra definición da 0.
select 'listados_compra_8_un_solo_abierto' as QUE_MIGRACION,
       (select count(*) from pg_indexes
         where schemaname = 'public'
           and indexname = 'listados_compra_un_borrador_por_dia_idx') as viejo_de_0,
       (select count(*) from pg_indexes
         where schemaname = 'public'
           and indexname = 'listados_compra_un_solo_abierto_idx'
           and indexdef like 'CREATE UNIQUE INDEX%'
           and indexdef like '%WHERE (estado = ''borrador''::text)%') as nuevo_de_1,
       (select count(*) from pg_indexes
         where schemaname = 'public'
           and indexname = 'listados_compra_un_solo_abierto_idx'
           and indexdef like '%(true)%') as sobre_constante_de_1,
       (select count(*) from listados_compra where estado = 'borrador') as abiertos,
       (select count(*) from listados_compra) as POBLACION_listados,
       (select max(fecha_operacion) from pedidos) as testigo_ultimo_pedido;
