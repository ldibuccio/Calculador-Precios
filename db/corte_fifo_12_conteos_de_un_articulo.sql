-- TODOS los conteos de un articulo, con la foto del sistema que quedo
-- congelada en cada uno. stock_sistema se escribe UNA vez al cargar el
-- conteo y no se recalcula nunca: comparar contra el numero de hoy es
-- comparar dos momentos distintos.
-- ficha NULL = los SUELTOS (cajones). Con ficha = las cajas de esa ficha.
-- Cambiar 'mango' por el articulo que se quiera mirar.
select (cs.creado_en at time zone 'America/Argentina/Buenos_Aires')::timestamp(0)
   as contado_el,
 a.nombre as articulo,
 case when cs.ficha_id is null then 'SUELTOS'
      else coalesce(f.codigo_cliente, f.nombre_cliente, 'ficha ' || f.id::text)
 end as porcion,
 cs.cantidad as conto,
 cs.stock_sistema as sistema_en_ese_momento,
 cs.cantidad - cs.stock_sistema as diferencia,
 row_number() over (partition by cs.ficha_id is null
   order by cs.creado_en desc) as es_el_ultimo_de_su_porcion
from conteos_stock cs
join articulos a on a.id = cs.articulo_id
left join fichas_logistica f on f.id = cs.ficha_id
where a.nombre ilike '%mango%'
order by cs.creado_en desc;
