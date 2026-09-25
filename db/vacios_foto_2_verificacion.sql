select
  'vacios_foto' as QUE_MIGRACION,
  (select count(*) from information_schema.tables where table_name = 'vacios_deposito_foto') as tabla,
  (select count(*) from vacios_deposito_foto) as fotos,
  (select count(*) from proveedores) as proveedores_POBLACION,
  (select count(distinct fecha) from vacios_deposito_foto) as fechas_distintas_1,
  (select coalesce(sum(cantidad), 0) from vacios_deposito_foto)::int as FOTO_total,
  (select count(*) from vacios_deposito_foto where cantidad < 0) as fotos_negativas,
  (select count(*) from vacios_deposito_foto f
    where f.cantidad = 0 and exists (select 1 from compras c
      where c.proveedor_id = f.proveedor_id and c.estado = 'recepcionado')) as en_cero_con_recepciones,
  (select max(procesada_el)::date from compras where estado = 'recepcionado') as ultima_recepcion;

-- Aparte del `do`, en las DOS bases. Bueno: tabla 1 · fotos = población ·
-- fechas 1 · FOTO_total = el 1.758 de hoy en Frutamax y 0 en Palmala.
-- `fotos_negativas` y `en_cero_con_recepciones` no tienen que dar 0: son los
-- proveedores que quedaron con el número mal y se arreglan con un ajuste.
