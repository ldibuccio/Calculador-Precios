-- ############################################################################
-- LAS FICHAS CON SU ENVASE Y SU KILAJE. Solo lectura.
--
-- Para decidir si el selector de Reproceso puede decir "Caja 6 kg — Día" en
-- vez del código del cliente ("TOM RED 1° E"). Lo que hay que mirar:
--
--   * `envase` en "(SIN ENVASE CARGADO)"  -> esa ficha no tiene de dónde
--     sacar la palabra "Caja". El campo es opcional en la base.
--   * `contenido_caja` en NULL            -> tampoco hay kilaje que mostrar.
--   * `fichas_de_ese_cliente` > 1 con el MISMO envase y el MISMO kilaje
--     -> ahí el envase no alcanza para distinguirlas y hace falta el código
--     del cliente igual. Es el mismo escalón que el Remanente.
-- ############################################################################
select a.nombre articulo, cl.nombre cliente, f.id ficha_id,
       coalesce(nullif(btrim(f.nombre_cliente),''),'(sin nombre propio)') nombre_del_cliente,
       coalesce(e.nombre,'(SIN ENVASE CARGADO)') envase,
       f.contenido_caja, f.unidad_venta, f.envase_variable,
       count(*) over (partition by f.cliente_id, f.articulo_id) fichas_de_ese_cliente
from fichas_logistica f
join articulos a on a.id = f.articulo_id
join clientes cl on cl.id = f.cliente_id
left join envases e on e.id = f.envase_id
order by cl.nombre, a.nombre, f.contenido_caja nulls first, f.id;
