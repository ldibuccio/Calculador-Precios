-- KILAJE INFLADO: renglones donde el contenido por bulto REAL quedó muy por
-- encima del de la ficha. Solo lectura. La sospecha: si alguien mandó más
-- bultos de los pedidos, hoy lo único que puede hacer para facturarlo es
-- inflar el kilaje, porque la cantidad armada no acepta más de lo pedido.
-- Las fichas de envase VARIABLE (mango, cherry) salen marcadas aparte: ahí
-- que el kilaje varíe es normal y no prueba nada.
with vig as (
  select distinct on (cliente_id, fecha_operacion) id, cliente_id, fecha_operacion
  from pedidos where anulado_el is null
  order by cliente_id, fecha_operacion, creado_en desc),
r as (
  select pr.id, v.fecha_operacion f, a.nombre articulo,
         coalesce(nullif(btrim(fl.nombre_cliente),''), a.nombre) ficha,
         cl.nombre cliente, fl.unidad_venta, fl.envase_variable var,
         pr.sucursal, pr.cantidad pedidos,
         coalesce(pr.cantidad_armada, pr.cantidad) bultos,
         pr.kilos_enviados kilos, fl.contenido_caja ficha_por_bulto
  from pedidos_renglones pr
  join vig v on v.id = pr.pedido_id
  join articulos a on a.id = pr.articulo_id
  join fichas_logistica fl on fl.id = pr.ficha_id
  left join clientes cl on cl.id = v.cliente_id
  where pr.armado_el is not null and pr.anulado_el is null
    and pr.kilos_enviados is not null and fl.contenido_caja > 0
    and coalesce(pr.cantidad_armada, pr.cantidad) > 0)
select f fecha, articulo, ficha, cliente, sucursal, unidad_venta,
       pedidos, bultos, kilos,
       round(kilos / bultos, 2) real_por_bulto,
       ficha_por_bulto,
       round(kilos / bultos / ficha_por_bulto, 2) veces,
       round(bultos * (kilos / bultos / ficha_por_bulto - 1), 1) bultos_de_mas,
       case when var then 'envase variable: normal que varie' else '' end nota
from r
where kilos / bultos > ficha_por_bulto * 1.15
order by var, kilos / bultos / ficha_por_bulto desc, 1 desc;
