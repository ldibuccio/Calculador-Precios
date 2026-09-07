-- ############################################################################
-- LAS FICHAS A LAS QUE LES FALTA EL ENVASE. Solo lectura.
--
-- Es la lista para cargarlas de una sentada desde Fichas Logísticas (el
-- formulario ya tiene el select de Envase, no hay que construir nada).
--
-- Ordenada por cliente y artículo, que es como se va a ir tildando.
--
-- La columna `ya_aparece_asi` muestra el texto exacto que el selector le está
-- mostrando hoy al operario, para poder ir cotejando contra la pantalla.
-- ############################################################################
select cl.nombre cliente,
       a.nombre articulo,
       f.id ficha_id,
       coalesce(nullif(btrim(f.nombre_cliente), ''), '(sin nombre propio)') codigo_del_cliente,
       f.contenido_caja,
       f.unidad_venta,
       coalesce(nullif(btrim(f.nombre_cliente), ''), '(sin nombre propio)')
         || case when f.contenido_caja is not null
                 then ' — ' || f.contenido_caja || ' ' ||
                      case f.unidad_venta when 'kilo' then 'kg'
                                          when 'unidad' then 'u'
                                          when 'cubeta' then 'cub.' else '' end
                 else '' end
         || ' — falta cargar el envase' ya_aparece_asi
from fichas_logistica f
join articulos a on a.id = f.articulo_id
join clientes cl on cl.id = f.cliente_id
where f.envase_id is null
order by cl.nombre, a.nombre, f.id;
