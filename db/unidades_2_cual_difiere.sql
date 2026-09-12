-- CUÁL es el par donde la unidad de compra y la de venta no coinciden.
--
-- `unidades_1` dio `difieren 1` en una de las dos bases. Esto lo muestra con
-- el nombre a la vista, para decidir si es un error de carga (se corrige y
-- listo) o un caso real de negocio (y entonces el costo de ese artículo
-- viene mal desde siempre, porque `_costear_compras` divide plata de COMPRA
-- por contenido de COMPRA y llama al resultado "costo por unidad de VENTA").
--
-- ACÁ SÍ VA UNA LISTA y no un conteo, porque la pregunta cambió: ya sabemos
-- cuántos hay, queremos ver cuál. Pero la consulta DEVUELVE UNA FILA IGUAL
-- cuando no hay ninguno (el `left join` sobre el ancla), con `total 0` y
-- todo lo demás en NULL: sin eso, "acá no hay" y "no se corrió" serían la
-- misma pantalla vacía -- y esto se corre en las DOS bases, donde una de
-- las dos no tiene ofensores.
--
-- `compras_60d` y `precios_cargados` contestan "¿este par se usa?": un par
-- que difiere y nunca se compró ni se le puso precio es un error de carga
-- dormido; uno con compras Y precio es plata que ya se calculó mal.
with pares as (
    select a.id            as articulo_id,
           a.nombre        as articulo,
           a.unidad_compra,
           f.id            as ficha_id,
           f.unidad_venta,
           coalesce(f.nombre_cliente, cl.nombre) as cliente,
           f.codigo_cliente,
           f.contenido_caja
    from articulos a
    join fichas_logistica f on f.articulo_id = a.id
    join clientes cl on cl.id = f.cliente_id
    where a.activo
),
ofensores as (
    select p.*,
           (select count(*) from compras c
             where c.articulo_id = p.articulo_id
               and c.fecha_operacion >= current_date - 60)          as compras_60d,
           (select count(*) from precios_venta_historial v
             where v.ficha_id = p.ficha_id)                         as precios_cargados,
           (select count(*) from pedidos_renglones r
             where r.ficha_id = p.ficha_id and r.anulado_el is null) as renglones_pedido
    from pares p
    where p.unidad_compra is not null
      and p.unidad_compra is distinct from p.unidad_venta
)
select (select count(*) from ofensores) as total,
       o.articulo_id, o.articulo, o.unidad_compra,
       o.ficha_id, o.cliente, o.codigo_cliente, o.unidad_venta, o.contenido_caja,
       o.compras_60d, o.precios_cargados, o.renglones_pedido
from (select 1) ancla
left join ofensores o on true
order by o.articulo;
