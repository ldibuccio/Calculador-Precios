-- Verificación del "por bulto" de los renglones. SE CORRE APARTE del bloque.
-- Tiene que dar: cargas_compra_5_por_bulto · 1 · 1 · 1 · <renglones> · <fecha>.
-- No nombra la columna nueva: así, corrida ANTES del bloque da 0 · 0 · 0 en
-- vez de un error, y "no corrió" se ve en la misma fila que "corrió".
select 'cargas_compra_5_por_bulto' as QUE_MIGRACION,
       (select count(*) from information_schema.columns
         where table_schema = 'public' and table_name = 'cargas_compra_renglones'
           and column_name = 'contenido_por_bulto') as columna_de_1,
       (select count(*) from pg_constraint
         where conname = 'cargas_compra_renglones_por_bulto_check') as guarda_de_1,
       -- POR DEFINICION y no por nombre: el nombre existe en cualquier
       -- versión del CHECK; lo que tiene que estar es el "> 0".
       (select count(*) from pg_constraint
         where conname = 'cargas_compra_renglones_por_bulto_check'
           and pg_get_constraintdef(oid) like '%> (0)::numeric%') as guarda_mayor_a_cero_de_1,
       (select count(*) from cargas_compra_renglones) as POBLACION_renglones,
       (select max(fecha_operacion) from pedidos) as testigo_ultimo_pedido;
