-- Verificación del bloque 3. SE CORRE APARTE: pegada a un `do` el editor se
-- queda con la última y el bloque NO SE EJECUTA, sin error y con "no rows".
-- Las DOS columnas de guarda van separadas porque el constraint CAMBIA DE
-- NOMBRE: un "¿existe alguno?" daría 1 en los dos estados.
select 'pase_a_segunda_con_ficha' as QUE_MIGRACION,
       (select count(*) from pg_constraint
         where conname = 'movimientos_stock_ficha_solo_merma_o_pase') as guarda_nueva_de_1,
       (select count(*) from pg_constraint
         where conname = 'movimientos_stock_ficha_solo_merma') as guarda_vieja_de_0,
       (select count(*) from movimientos_stock
         where tipo = 'pase_a_segunda' and ficha_id is not null
           and anulado_el is null) as pases_con_ficha,
       (select count(*) from movimientos_stock
         where anulado_el is null) as POBLACION_movimientos,
       (select max(fecha_operacion) from reprocesos where anulado_el is null)
           as testigo_ultima_guia_r;
