select 'vacios_marca_texto_2_sena_tarde' as que_migracion,
  count(*) filter (where coalesce(sena, 0) > 0 and btrim(coalesce(marca, '')) <> ''
                     and marca_vacio_id is null) as faltan_vincular,
  count(*) filter (where id = 921 and marca_vacio_id is not null) as la_921_vinculada,
  (select count(*) from marcas_vacio) as marcas,
  count(*) as compras_recibidas,
  max(procesada_el) as ultima_recepcion
from compras
where estado = 'recepcionado';

-- Se corre DESPUÉS del bloque, aparte. faltan_vincular tiene que dar 0.
-- la_921_vinculada: 1 en Frutamax (Saturno, marca Camila), 0 en Palmala.
