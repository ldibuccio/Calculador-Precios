select 'vales_papel' as QUE_MIGRACION,
       (select count(*) from vales_a_cobrar
         where origen = 'anterior_al_sistema') as vales_en_papel,
       (select coalesce(sum(importe), 0) from vales_a_cobrar
         where origen = 'anterior_al_sistema') as plata_en_papel,
       (select count(*) from vales_papel_listado) as listado_pendiente_en_0,
       (select count(*) from vales_a_cobrar) as POBLACION_vales,
       (select max(creado_en) from vales_a_cobrar
         where origen = 'anterior_al_sistema') as testigo_ultima_carga;

-- VALES ANTERIORES AL SISTEMA, paso 4 de 4: VERIFICAR, aparte del paso 3.
-- Pegada al do, el editor se queda con la ultima y el do NO SE EJECUTA.
-- Si la carga corrio: vales_en_papel subio en las filas que la revision
-- conto, listado_pendiente_en_0 da 0 y el testigo es de recien. El editor
-- no muestra el NOTICE del do: lo que confirma es esta consulta.
