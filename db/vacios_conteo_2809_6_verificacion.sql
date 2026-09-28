with a as (
  select id, creado_en from vacios_deposito_arranques
   where motivo = 'Conteo físico 28/09' order by id desc limit 1
),
cargadas as (
  select ap.proveedor_id, ap.marca_vacio_id, ap.cantidad, mv.nombre_normalizado
    from vacios_deposito_arranque_pilas ap
    join a on a.id = ap.arranque_id
    left join marcas_vacio mv on mv.id = ap.marca_vacio_id
),
despues as (
  select sum(c) as c from (
    select cantidad as c from cargadas
    union all
    select coalesce(co.cantidad_cajones_real, co.cantidad_cajones) from compras co, a
     where co.estado = 'recepcionado' and coalesce(co.sena, 0) > 0 and co.procesada_el > a.creado_en
    union all
    select -d.cantidad from vacios_deposito_devoluciones d, a
     where d.anulado_el is null and d.creado_en > a.creado_en
    union all
    select x.cantidad from vacios_deposito_ajustes x, a
     where x.anulado_el is null and x.creado_en > a.creado_en
  ) s
)
select 'vacios_conteo_2809_5_cargar' as que_migracion,
  (select count(*) from vacios_deposito_arranques where motivo = 'Conteo físico 28/09') as arranques_1,
  (select count(*) from cargadas) as pilas_17,
  (select coalesce(sum(cantidad), 0) from cargadas) as total_1070,
  (select count(*) from vacios_conteo_2809() t
     join cargadas c on c.proveedor_id = (select proveedor_id from vacios_conteo_2809_proveedor(t.pn))
      and c.nombre_normalizado = lower(translate(t.marca, 'áéíóúñÁÉÍÓÚÑ', 'aeiounAEIOUN'))
      and c.cantidad = t.cant) as filas_iguales_17,
  (select count(*) from proveedores where codigo_puesto = 'N00P00' and nombre = 'Sin Proveedor')
    as sin_proveedor_1,
  (select c from despues) as stock_ahora,
  (select to_char(creado_en at time zone 'America/Argentina/Buenos_Aires', 'DD/MM HH24:MI') from a)
    as arranco,
  (select to_char(max(procesada_el) at time zone 'America/Argentina/Buenos_Aires', 'DD/MM HH24:MI')
     from compras where estado = 'recepcionado') as ultima_recepcion;

-- VERIFICACIÓN del arranque de vacíos del 28/09. Se corre APARTE del do del
-- bloque 5, en otra corrida, y en las dos bases. En Frutamax: arranques 1,
-- pilas 17, total 1070, filas_iguales 17, sin_proveedor 1, y stock_ahora
-- 1070 si no entró ni salió nada después (si no, 1070 ± eso). En Palmala:
-- todo en 0 y stock_ahora vacío, porque ahí el bloque 5 no hace nada.
