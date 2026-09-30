with c as (select fecha from corte_modelo where id = 1),
r as (
  select cl.nombre as cliente, r.cantidad, r.armado_el, r.cantidad_armada,
         r.ficha_id, r.agregado_a_mano_el,
         exists (select 1 from fichas_logistica f where f.cliente_id = p.cliente_id
                 and f.articulo_id = r.articulo_id) as hay_ficha_hoy
  from pedidos_renglones r
  join pedidos p on p.id = r.pedido_id
  join clientes cl on cl.id = p.cliente_id
  where p.anulado_el is null and r.anulado_el is null
    and r.articulo_id is not null
    and p.fecha_operacion > (select fecha from c)
)
select * from (
select 0 as orden, 'TOTAL' as cliente,
       (select fecha from c) as corte,
       count(*) filter (where ficha_id is null) as sin_ficha,
       count(*) filter (where ficha_id is null and armado_el is not null
                        and coalesce(cantidad_armada, cantidad) > 0) as sin_ficha_ARMADOS,
       coalesce(sum(coalesce(cantidad_armada, cantidad)) filter (
         where ficha_id is null and armado_el is not null), 0) as bultos_armados,
       count(*) filter (where ficha_id is null and cantidad = 0) as sin_ficha_EN_CERO,
       count(*) filter (where ficha_id is null and agregado_a_mano_el is not null)
         as sin_ficha_A_MANO,
       count(*) filter (where ficha_id is null and hay_ficha_hoy) as HAY_FICHA_HOY,
       count(*) as renglones_POBLACION,
       (select max(armado_el)::date from pedidos_renglones) as ultimo_armado
from r
union all
select 1, cliente, null, count(*), count(*) filter (where armado_el is not null
         and coalesce(cantidad_armada, cantidad) > 0),
       coalesce(sum(coalesce(cantidad_armada, cantidad)) filter (
         where armado_el is not null), 0),
       count(*) filter (where cantidad = 0),
       count(*) filter (where agregado_a_mano_el is not null),
       count(*) filter (where hay_ficha_hoy),
       null, null
from r where ficha_id is null
group by cliente
) x
order by orden, sin_ficha desc;

-- SOLO LECTURA. Renglones SIN FICHA desde el corte, por cliente. La fila
-- TOTAL sale siempre, con la población y el último armado al lado.
-- ARMADOS: los que salieron. EN_CERO: sin cantidad. A_MANO: agregados a
-- mano. HAY_FICHA_HOY: el cliente tiene hoy ficha de ese artículo, o sea
-- que la del renglón se borró o se le cambió el artículo.
