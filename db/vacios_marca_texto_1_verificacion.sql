with c as (
  select c.*, f.creado_en as foto
    from compras c
    left join vacios_deposito_foto f on f.proveedor_id = c.proveedor_id
   where c.estado = 'recepcionado' and c.procesada_el is not null
     and (f.creado_en is null or c.procesada_el > f.creado_en)
)
select 'vacios_marca_texto_1_vincular' as que_migracion,
  count(*) filter (where coalesce(sena, 0) > 0 and btrim(coalesce(marca, '')) <> ''
                     and marca_vacio_id is null) as faltan_vincular,
  count(*) filter (where marca_vacio_id is not null) as vinculadas,
  count(*) filter (where coalesce(sena, 0) = 0 and btrim(coalesce(marca, '')) <> '')
    as con_marca_sin_sena,
  (select count(*) from marcas_vacio) as marcas,
  count(*) as recibidas_desde_la_foto,
  max(procesada_el) as ultima_recepcion
from c;

-- Se corre DESPUÉS del bloque, aparte. faltan_vincular tiene que dar 0.
-- con_marca_sin_sena no se vincula a propósito: sin seña no entra a Vacíos.
