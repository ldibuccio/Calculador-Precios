select
  g.id as guia, g.fecha_operacion as fecha, p.nombre as proveedor,
  f.foto_ruta,
  case when f.foto_ruta ~ ('/guia-' || g.id || '-')
       then 'SUBIDA desde la compra (Fotos de la guía)'
       else 'COMANDA de Compras (carga del Puesto)' end as de_donde,
  (f.creado_en at time zone 'America/Argentina/Buenos_Aires')::timestamp(0) as foto_subida,
  (select string_agg(c.id || ' ' || a.nombre || ' (cargada '
            || to_char(c.cargado_el at time zone 'America/Argentina/Buenos_Aires', 'DD/MM HH24:MI') || ')', ' · ')
     from compras c join articulos a on a.id = c.articulo_id
    where c.guia_id = g.id) as compras_en_la_guia,
  (select gc.id from guias_compra gc
    where gc.fecha_operacion = g.fecha_operacion and gc.proveedor_id = g.proveedor_id
      and not gc.de_deposito) as guia_de_compras_ese_dia,
  (select count(*) from compras_eliminadas e
    where (e.fila->>'guia_id')::bigint = g.id) as borradas_de_esta_guia,
  (select count(*) from guias_compra g2 where g2.de_deposito
      and exists (select 1 from fotos_guia f2 where f2.guia_id = g2.id)) as TOTAL_esperado
from guias_compra g
join fotos_guia f on f.guia_id = g.id
join proveedores p on p.id = g.proveedor_id
where g.de_deposito
order by g.id, f.creado_en;

-- SOLO LECTURA. Lista cada foto que quedó colgada de una guía de DEPÓSITO
-- (guia_deposito_4 dio deposito_con_fotos 2 en Frutamax y 1 en Palmala).
-- `TOTAL_esperado` es el conteo de guías de la verificación, en cada fila:
-- si la lista sale vacía con ese número en más de 0, la consulta está mal.
--
-- LA RUTA DICE DE DÓNDE VINO la foto (core/storage.py pone la base en el
-- nombre del archivo):
--   · `.../guia-<id>-...`  -> la subieron desde Fotos de la guía de UNA
--     compra de esta guía. Es del ingreso directo y está bien donde está.
--   · otra base (código de puesto, "listado") -> es una COMANDA de Compras.
--     Llegó cuando la guía todavía era compartida, y la compra de Compras
--     que la trajo ya no está en esta guía: se borró (`borradas_de_esta_
--     guia`) o se movió de día o de proveedor.
