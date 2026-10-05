do $$
declare
  norm text := $q$lower(regexp_replace(translate(btrim(%s),
    'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüýÿĀāĂăĄąĆćĈĉĊċČčĎďĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĨĩĪīĬĭĮįİĴĵĶķĹĺĻļĽľŃńŅņŇňŌōŎŏŐőŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž',
    'AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuyyAaAaAaCcCcCcCcDdEeEeEeEeEeGgGgGgGgHhIiIiIiIiIJjKkLlLlLlNnNnNnOoOoOoRrRrRrSsSsSsSsTtTtUuUuUuUuUuUuWwYyYZzZzZz'), '\s+', ' ', 'g'))$q$;
  cond text := $q$c.estado = 'recepcionado' and coalesce(c.sena, 0) > 0
    and c.marca_vacio_id is null and btrim(coalesce(c.marca, '')) <> ''$q$;
  n_tocadas int;
  n_marcas int;
  n_compras int;
begin
  execute format($f$select count(*) from compras c where %s and (
      exists (select 1 from vacios_deposito_asignaciones s
               where s.proveedor_id = c.proveedor_id and s.marca_desde_id is null
                 and s.anulado_el is null and s.creado_en > c.procesada_el)
   or exists (select 1 from vacios_deposito_devoluciones d
               where d.proveedor_id = c.proveedor_id and d.marca_vacio_id is null
                 and d.anulado_el is null and d.creado_en > c.procesada_el))$f$, cond)
    into n_tocadas;
  if n_tocadas > 0 then
    raise exception 'ABORTA: % compras con cajones ya movidos desde sin asignar', n_tocadas;
  end if;
  execute format($f$insert into marcas_vacio (proveedor_id, nombre, nombre_normalizado)
    select distinct on (c.proveedor_id, %1$s) c.proveedor_id,
           regexp_replace(btrim(c.marca), '\s+', ' ', 'g'), %1$s
      from compras c where %2$s
     order by c.proveedor_id, %1$s, c.procesada_el
    on conflict (proveedor_id, nombre_normalizado) do nothing$f$,
    format(norm, 'c.marca'), cond);
  get diagnostics n_marcas = row_count;
  execute format($f$update compras c set marca_vacio_id = m.id from marcas_vacio m
     where m.proveedor_id = c.proveedor_id and m.nombre_normalizado = %1$s
       and %2$s$f$, format(norm, 'c.marca'), cond);
  get diagnostics n_compras = row_count;
  raise notice 'marcas creadas %, compras vinculadas %', n_marcas, n_compras;
end $$;

-- SEÑA CARGADA DESPUÉS (05/10): los cajones iban a "sin asignar" con
-- la marca escrita. La pega a su marca de cajón. Aborta si esos cajones
-- ya salieron de "sin asignar" (se contarían dos veces). Idempotente.
-- Verificación APARTE: vacios_marca_texto_2_verificacion.sql.
