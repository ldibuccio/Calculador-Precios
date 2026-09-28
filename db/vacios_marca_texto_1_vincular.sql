do $$
declare
  norm text := $q$lower(regexp_replace(translate(btrim(%s),
    'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüýÿĀāĂăĄąĆćĈĉĊċČčĎďĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĨĩĪīĬĭĮįİĴĵĶķĹĺĻļĽľŃńŅņŇňŌōŎŏŐőŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž',
    'AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuyyAaAaAaCcCcCcCcDdEeEeEeEeEeGgGgGgGgHhIiIiIiIiIJjKkLlLlLlNnNnNnOoOoOoRrRrRrSsSsSsSsTtTtUuUuUuUuUuUuWwYyYZzZzZz'), '\s+', ' ', 'g'))$q$;
  cond text := $q$c.estado = 'recepcionado' and c.procesada_el is not null
    and coalesce(c.sena, 0) > 0 and c.marca_vacio_id is null
    and btrim(coalesce(c.marca, '')) <> ''
    and (f.creado_en is null or c.procesada_el > f.creado_en)$q$;
  n_marcas int;
  n_compras int;
begin
  execute format($f$insert into marcas_vacio (proveedor_id, nombre, nombre_normalizado)
    select distinct on (c.proveedor_id, %1$s) c.proveedor_id,
           regexp_replace(btrim(c.marca), '\s+', ' ', 'g'), %1$s
      from compras c
      left join vacios_deposito_foto f on f.proveedor_id = c.proveedor_id
     where %2$s
     order by c.proveedor_id, %1$s, c.procesada_el
    on conflict (proveedor_id, nombre_normalizado) do nothing$f$,
    format(norm, 'c.marca'), cond);
  get diagnostics n_marcas = row_count;
  execute format($f$update compras c set marca_vacio_id = m.id
      from marcas_vacio m, compras x
      left join vacios_deposito_foto f on f.proveedor_id = x.proveedor_id
     where x.id = c.id and m.proveedor_id = c.proveedor_id
       and m.nombre_normalizado = %1$s and %2$s$f$,
    format(norm, 'c.marca'), cond);
  get diagnostics n_compras = row_count;
  comment on table marcas_vacio is 'Marcas de cajón de cada proveedor. Las crea Recepción al escribir la marca (con seña) o Administración al asignar.';
  raise notice 'marcas creadas %, compras vinculadas %', n_marcas, n_compras;
end $$;

-- VINCULA LA MARCA ESCRITA AL RECIBIR CON SU MARCA DE CAJÓN (28/09).
-- 25 de 27 compras desde la foto tienen compras.marca escrita y
-- marca_vacio_id en NULL: la marca del cajón solo se elegía de las
-- cargadas en Vacíos, y no había ninguna. Crea la marca por proveedor
-- (plegada como normalizar_texto) y la pega a la compra.
-- Solo las que suma el stock de Vacíos: recibidas CON SEÑA después de
-- la foto. Idempotente. Verificación APARTE:
-- vacios_marca_texto_1_verificacion.sql.
