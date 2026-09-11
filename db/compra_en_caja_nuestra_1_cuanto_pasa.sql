-- ¿Cuánto volumen tendría una pantalla para "la compra ya viene en caja
-- nuestra"? Se corre ANTES de construir: si son dos casos, alcanza con
-- cargar la compra y la guía R a mano, como ya se puede hoy.
--
-- ES UN PROXY Y HAY QUE LEERLO COMO TAL. El caso nuevo NO está registrado
-- en ningún lado —hoy no existe— así que no se puede contar directo. Lo que
-- se cuenta es su HUELLA: una compra recepcionada y una guía R del MISMO
-- artículo el MISMO día. El caso nuevo se ve así; el circuito normal
-- también, cuando el cajón se trabaja el día que llega.
--
-- O sea que es un TECHO, no el número. Sirve para decidir en una sola
-- dirección: si el techo es chico, la pantalla no hace falta — no puede
-- haber más casos nuevos que esto. Si es grande, no prueba nada y hay que
-- preguntarle a Lionel cuáles son.
--
-- Desde el corte: antes de esa fecha el modelo es otro.

with c0 as (select fecha as f0 from corte_modelo where id = 1),
c as (
  select fecha_operacion as f, articulo_id as a, proveedor_id as p
  from compras
  where estado = 'recepcionado' and cantidad_cajones_real is not null
    and fecha_operacion > (select f0 from c0)
), r as (
  select distinct fecha_operacion as f, articulo_id as a
  from reprocesos where anulado_el is null
    and fecha_operacion > (select f0 from c0)
), pares as (
  select c.f, c.a, c.p from c join r on r.f = c.f and r.a = c.a
)
select
  (select f0 from c0) as corte,
  (select count(*) from c) as compras_desde_el_corte,
  (select count(*) from pares) as compra_y_guia_el_mismo_dia,
  (select count(distinct p) from pares) as proveedores,
  (select count(distinct a) from pares) as articulos,
  (select count(distinct f) from pares) as dias,
  (select string_agg(distinct p::text || '/' || a::text, ' · ')
     from (select * from pares limit 15) d) as prov_articulo,
  (select max(fecha_operacion) from compras) as ultima_compra;
